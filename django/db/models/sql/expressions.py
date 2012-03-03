from django.core.exceptions import FieldError
from django.db.models.fields import FieldDoesNotExist
from django.db.models.fields import IntegerField, FloatField
from django.db.models.sql.constants import LOOKUP_SEP

# Fake fields used to identify aggregate types in data-conversion operations.
ordinal_aggregate_field = IntegerField()
computed_aggregate_field = FloatField()

class SQLEvaluator(object):
    def __init__(self, expression, query, allow_joins=True):
        self.expression = expression
        self.opts = query.get_meta()
        self.cols = {}

        self.contains_aggregate = False
        self.field = self.expression.prepare(self, query, allow_joins)

    def prepare(self):
        return self

    def as_sql(self, qn, connection):
        return self.expression.evaluate(self, qn, connection)

    def relabel_aliases(self, change_map):
        for node, col in self.cols.items():
            if hasattr(col, "relabel_aliases"):
                col.relabel_aliases(change_map)
            else:
                self.cols[node] = (change_map.get(col[0], col[0]), col[1])

    #####################################################
    # Vistor methods for initial expression preparation #
    #####################################################

    def prepare_node(self, node, query, allow_joins):
        cols = []
        for child in node.children:
            if hasattr(child, 'prepare'):
                cols.append(child.prepare(self, query, allow_joins))

        # The final type of this expression will come from two things:
        # * the type of the node (for nodes with computed/ordinal properties),
        # * the combined type of all columns (if they are of distinct types)
        # The type of this field will be used to coerce values
        # retrieved from the database.

        def coerce_types(acc, nxt):
            # All the same? that type.
            if acc is None or acc.get_internal_type() == nxt.get_internal_type():
                return nxt
            # Integers coerce to Decimals, which both coerce to Floats.
            a_t = acc.get_internal_type()
            n_t = nxt.get_internal_type()
            if {a_t, n_t} == {'IntegerField', 'DecimalField'}:
                return {a_t: acc, n_t: nxt}['DecimalField']
            if {a_t, n_t} == {'FloatField', 'DecimalField'}:
                return computed_aggregate_field
            if {a_t, n_t} == {'IntegerField', 'FloatField'}:
                return computed_aggregate_field
            raise TypeError("Can't resolve type coercion of %s and %s" % (a_t, n_t))

        if getattr(node, 'is_ordinal', False):
            return ordinal_aggregate_field
        elif getattr(node, 'is_computed', False):
            return computed_aggregate_field
        else:
            col = reduce(coerce_types, cols, None)
            return col

    def prepare_leaf(self, node, query, allow_joins):
        if not allow_joins and LOOKUP_SEP in node.name:
            raise FieldError("Joined field references are not permitted in this query")

        field_list = node.name.split(LOOKUP_SEP)
        if (len(field_list) == 1 and
                node.name in query.aggregates and (
                query.aggregate_select_mask is None or
                node.name in query.aggregate_select_mask)):
            self.contains_aggregate = True
            source = query.aggregates[node.name].field
            self.cols[node] = node.name
        elif ((len(field_list) > 1) or 
                (field_list[0] not in [i.name for i in self.opts.fields]) or 
                query.group_by is None or 
                not getattr(self,'is_summary',False)):
            try:
                field, source, opts, join_list, last, _ = query.setup_joins(
                    field_list, query.get_meta(),
                    query.get_initial_alias(), False)
                col, _, join_list = query.trim_joins(source, join_list, last, False)

                # If the aggregate references a model or field that requires a join, 
                # those joins must be LEFT OUTER - empty join rows must be returned 
                # in order for zeros to be returned for those aggregates. 
                for column_alias in join_list: 
                    query.promote_alias(column_alias, unconditional=True)

                self.cols[node] = (join_list[-1], col)
            except FieldDoesNotExist:
                raise FieldError("Cannot resolve keyword %r into field. "
                                 "Choices are: %s" % (self.name,
                                                      [f.name for f in self.opts.fields]))
        else:
            # The simplest cases. No joins required - 
            # just reference the provided column alias. 
            field_name = field_list[0] 
            source = self.opts.get_field(field_name) 
            self.cols[node] = field_name 
        return source

    ##################################################
    # Vistor methods for final expression evaluation #
    ##################################################

    def evaluate_node(self, node, qn, connection):
        expressions = []
        expression_params = []
        for child in node.children:
            if hasattr(child, 'evaluate'):
                sql, params = child.evaluate(self, qn, connection)
            else:
                sql, params = '%s', (child,)

            if len(getattr(child, 'children', [])) > 1:
                format = '(%s)'
            else:
                format = '%s'

            if sql:
                expressions.append(format % sql)
                expression_params.extend(params)

        infix = getattr(node, 'infix', True)
        par = getattr(node, 'takes_parens', True)
        return connection.ops.combine_expression(node.connector, expressions, infix, par), expression_params

    def evaluate_leaf(self, node, qn, connection):
        col = self.cols[node]
        if hasattr(col, 'as_sql'):
            result = col.as_sql(qn, connection)
            if isinstance(result, (tuple, list)):
                return result
            else:
                return result, ()
        elif isinstance(col, (tuple, list)):
            return '%s.%s' % (qn(col[0]), qn(col[1])), ()
        else:
            return col, ()

    def evaluate_date_modifier_node(self, node, qn, connection):
        timedelta = node.children.pop()
        sql, params = self.evaluate_node(node, qn, connection)

        if timedelta.days == 0 and timedelta.seconds == 0 and \
                timedelta.microseconds == 0:
            return sql, params

        return connection.ops.date_interval_sql(sql, node.connector, timedelta), params
