#
# Licensed to the Apache Software Foundation (ASF) under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# The ASF licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import unittest

from pyspark.pandas.tests.plot.test_frame_plot_matplotlib import DataFramePlotMatplotlibTestsMixin
from pyspark.testing.connectutils import ReusedConnectTestCase
from pyspark.testing.pandasutils import PandasOnSparkTestUtils, TestUtils


class DataFramePlotMatplotlibParityTests(
    DataFramePlotMatplotlibTestsMixin, PandasOnSparkTestUtils, TestUtils, ReusedConnectTestCase
):
    @unittest.skip("TODO(SPARK-43711): Fix Transformer.transform to work with Spark Connect.")
    def test_hist_plot(self):
        super().test_hist_plot()

    @unittest.skip("TODO(SPARK-44372): Enable KernelDensity within Spark Connect.")
    def test_kde_plot(self):
        super().test_kde_plot()


if __name__ == "__main__":
    from pyspark.pandas.tests.connect.plot.test_parity_frame_plot_matplotlib import *  # noqa: F401

    try:
        import xmlrunner  # type: ignore[import]

        testRunner = xmlrunner.XMLTestRunner(output="target/test-reports", verbosity=2)
    except ImportError:
        testRunner = None
    unittest.main(testRunner=testRunner, verbosity=2)
