"""
Classes to represent the default SQL aggregate functions
"""

from django.db.models.sql import expressions

class Aggregate(expressions.SQLEvaluator):
    """
    Default SQL Aggregate.
    """

    def __init__(self, expression, query, is_summary=False, **extra):
        """Instantiate an SQL aggregate

         * expression is the aggregate query expression to be evaluated.
         * query is the backend-specific query instance to which the aggregate
           is to be added.
         * extra is a dictionary of additional data to provide for the
           aggregate definition

        Also utilizes the class variables:
         * is_ordinal, a boolean indicating if the output of this aggregate
           is an integer (e.g., a count)
         * is_computed, a boolean indicating if this output of this aggregate
           is a computed float (e.g., an average), regardless of the input
           type.

        """
        super(Aggregate, self).__init__(expression, query)
        self.is_summary = is_summary
        self.extra = extra

Avg = Aggregate
Count = Aggregate
Max = Aggregate
Min = Aggregate
StdDev = Aggregate
Sum = Aggregate
Variance = Aggregate
