"""
Classes to represent the definitions of aggregate functions.
"""

from django.db.models import expressions

class Aggregate(expressions.ExpressionNode):
    """
    Default Aggregate definition.
    """
    is_ordinal = False
    is_computed = False
    preserve_tree = True
    infix = False
    takes_parens = True

    def __init__(self, lookup, **extra):
        """Instantiate a new aggregate.

         * lookup is the field on which the aggregate operates.
         * extra is a dictionary of additional data to provide for the
           aggregate definition

        Also utilizes the class variables:
         * name, the identifier for this aggregate function.
        """
        self.lookup = lookup
        self.extra = extra
        if hasattr(self.lookup,'evaluate'):
            super(Aggregate, self).__init__([self.lookup], self.sql_function, False)
        else:
            super(Aggregate, self).__init__([expressions.F(self.lookup)], self.sql_function, False)

    @property
    def default_alias(self):
        if hasattr(self.lookup, 'default_alias'):
            alias = self.lookup.default_alias
        elif hasattr(self.lookup, 'evaluate'): 
            raise ValueError('When aggregating over an expression, you need to give an alias.') 
        else:
            alias = self.lookup
        return '%s__%s' % (alias, self.name.lower())

    def add_to_query(self, query, alias, is_summary):
        """Add the aggregate to the nominated query.

        This method is used to convert the generic Aggregate definition into a
        backend-specific definition.

         * query is the backend-specific query instance to which the aggregate
           is to be added.
         * is_summary is a boolean that is set True if the aggregate is a
           summary value rather than an annotation.
        """
        klass = getattr(query.aggregates_module, self.name)
        aggregate = klass(self, query, is_summary=is_summary, **self.extra)
        query.aggregates[alias] = aggregate

class Asterisk(object):
    def evaluate(self, evaluator, qn, connection):
        return '*', ()

class Distinct(Aggregate):
    name = 'Distinct'
    takes_parens = False
    sql_function = 'DISTINCT'

    @property
    def default_alias(self):
        return super(Distinct,self).default_alias.rpartition("__")[0]

class Avg(Aggregate):
    name = 'Avg'
    is_computed = True
    sql_function = 'AVG'

class Count(Aggregate):
    name = 'Count'
    is_ordinal = True
    sql_function = 'COUNT'

    def __init__(self, lookup, distinct=False, **extra):
        if lookup == '*':
            lookup = Asterisk()
        if distinct:
            lookup = Distinct(lookup)
        super(Count, self).__init__(lookup, **extra)

class Max(Aggregate):
    name = 'Max'
    sql_function = 'MAX'

class Min(Aggregate):
    name = 'Min'
    sql_function = 'MIN'

class StdDev(Aggregate):
    name = 'StdDev'
    is_computed = True

    @property
    def sql_function(self):
        return self.extra.get('sample',False) and 'STDDEV_SAMP' or 'STDDEV_POP'

class Sum(Aggregate):
    name = 'Sum'
    sql_function = 'SUM'

class Variance(Aggregate):
    name = 'Variance'
    is_computed = True

    @property
    def sql_function(self):
        return self.extra.get('sample',False) and 'VAR_SAMP' or 'VAR_POP'
