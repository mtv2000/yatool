import test.const
from test.test_types import library_ut


GTEST_TYPE = "gtest"


class GUnitTestSuite(library_ut.UnitTestSuite):
    """
    GTEST fully supports UNITTESTS's interface.
    """

    def get_type(self):
        return GTEST_TYPE

    @property
    def name(self):
        return GTEST_TYPE

    @property
    def class_type(self):
        return test.const.SuiteClassType.REGULAR
