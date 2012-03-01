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
            super(Aggregate, self).__init__([self.lookup], self.sql_template, False)
        else:
            super(Aggregate, self).__init__([expressions.F(self.lookup)], self.sql_template, False)

    @property
    def default_alias(self):
        if hasattr(self.lookup, 'evaluate'): 
            raise ValueError('When aggregating over an expression, you need to give an alias.') 
        return '%s__%s' % (self.lookup, self.name.lower())

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

class Avg(Aggregate):
    name = 'Avg'
    is_computed = True
    sql_template = 'AVG(%s)'

class Count(Aggregate):
    name = 'Count'
    is_ordinal = True

    @property
    def sql_template(self):
        return self.extra.get('distinct',False) and 'COUNT(DISTINCT %s)' or 'COUNT(%s)'

class Max(Aggregate):
    name = 'Max'
    sql_template = 'MAX(%s)'

class Min(Aggregate):
    name = 'Min'
    sql_template = 'MIN(%s)'

class StdDev(Aggregate):
    name = 'StdDev'
    is_computed = True

    @property
    def sql_template(self):
        return self.extra.get('sample',False) and 'STDDEV_SAMP(%s)' or 'STDDEV_POP(%s)'

class Sum(Aggregate):
    name = 'Sum'
    sql_template = 'SUM(%s)'

class Variance(Aggregate):
    name = 'Variance'
    is_computed = True

    @property
    def sql_template(self):
        return self.extra.get('sample',False) and 'VAR_SAMP(%s)' or 'VAR_POP(%s)'
