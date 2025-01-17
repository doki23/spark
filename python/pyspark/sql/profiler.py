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
from abc import ABC, abstractmethod
import os
import pstats
from threading import RLock
from typing import Dict, Optional, TYPE_CHECKING

from pyspark.accumulators import (
    Accumulator,
    AccumulatorParam,
    SpecialAccumulatorIds,
    _accumulatorRegistry,
)
from pyspark.profiler import CodeMapDict, MemoryProfiler, MemUsageParam, PStatsParam

if TYPE_CHECKING:
    from pyspark.sql._typing import ProfileResults


class _ProfileResultsParam(AccumulatorParam[Optional["ProfileResults"]]):
    """
    AccumulatorParam for profilers.
    """

    @staticmethod
    def zero(value: Optional["ProfileResults"]) -> Optional["ProfileResults"]:
        return value

    @staticmethod
    def addInPlace(
        value1: Optional["ProfileResults"], value2: Optional["ProfileResults"]
    ) -> Optional["ProfileResults"]:
        if value1 is None or len(value1) == 0:
            value1 = {}
        if value2 is None or len(value2) == 0:
            value2 = {}

        value = value1.copy()
        for key, (perf, mem, *_) in value2.items():
            if key in value1:
                orig_perf, orig_mem, *_ = value1[key]
            else:
                orig_perf, orig_mem = (PStatsParam.zero(None), MemUsageParam.zero(None))
            value[key] = (
                PStatsParam.addInPlace(orig_perf, perf),
                MemUsageParam.addInPlace(orig_mem, mem),
            )
        return value


ProfileResultsParam = _ProfileResultsParam()


class ProfilerCollector(ABC):
    """
    A base class of profiler collectors for session based profilers.

    This supports cProfiler and memory-profiler enabled by setting a SQL config
    `spark.sql.pyspark.udf.profiler` to "perf" or "memory".
    """

    def __init__(self) -> None:
        self._lock = RLock()

    def show_perf_profiles(self, id: Optional[int] = None) -> None:
        """
        Show the perf profile results.

        .. versionadded:: 4.0.0

        Parameters
        ----------
        id : int, optional
            A UDF ID to be shown. If not specified, all the results will be shown.
        """
        with self._lock:
            stats = self._perf_profile_results

        def show(id: int) -> None:
            s = stats.get(id)
            if s is not None:
                print("=" * 60)
                print(f"Profile of UDF<id={id}>")
                print("=" * 60)
                s.sort_stats("time", "cumulative").print_stats()

        if id is not None:
            show(id)
        else:
            for id in sorted(stats.keys()):
                show(id)

    @property
    def _perf_profile_results(self) -> Dict[int, pstats.Stats]:
        with self._lock:
            return {
                result_id: perf
                for result_id, (perf, _, *_) in self._profile_results.items()
                if perf is not None
            }

    def show_memory_profiles(self, id: Optional[int] = None) -> None:
        """
        Show the memory profile results.

        .. versionadded:: 4.0.0

        Parameters
        ----------
        id : int, optional
            A UDF ID to be shown. If not specified, all the results will be shown.
        """
        with self._lock:
            code_map = self._memory_profile_results

        def show(id: int) -> None:
            cm = code_map.get(id)
            if cm is not None:
                print("=" * 60)
                print(f"Profile of UDF<id={id}>")
                print("=" * 60)
                MemoryProfiler._show_results(cm)

        if id is not None:
            show(id)
        else:
            for id in sorted(code_map.keys()):
                show(id)

    @property
    def _memory_profile_results(self) -> Dict[int, CodeMapDict]:
        with self._lock:
            return {
                result_id: mem
                for result_id, (_, mem, *_) in self._profile_results.items()
                if mem is not None
            }

    @property
    @abstractmethod
    def _profile_results(self) -> "ProfileResults":
        """
        Get the profile results.
        """
        ...

    def dump_perf_profiles(self, path: str, id: Optional[int] = None) -> None:
        """
        Dump the perf profile results into directory `path`.

        .. versionadded:: 4.0.0

        Parameters
        ----------
        path: str
            A directory in which to dump the perf profile.
        id : int, optional
            A UDF ID to be shown. If not specified, all the results will be shown.
        """
        with self._lock:
            stats = self._perf_profile_results

        def dump(id: int) -> None:
            s = stats.get(id)

            if s is not None:
                if not os.path.exists(path):
                    os.makedirs(path)
                p = os.path.join(path, f"udf_{id}_perf.pstats")
                s.dump_stats(p)

        if id is not None:
            dump(id)
        else:
            for id in sorted(stats.keys()):
                dump(id)

    def dump_memory_profiles(self, path: str, id: Optional[int] = None) -> None:
        """
        Dump the memory profile results into directory `path`.

        .. versionadded:: 4.0.0

        Parameters
        ----------
        path: str
            A directory in which to dump the memory profile.
        id : int, optional
            A UDF ID to be shown. If not specified, all the results will be shown.
        """
        with self._lock:
            code_map = self._memory_profile_results

        def dump(id: int) -> None:
            cm = code_map.get(id)

            if cm is not None:
                if not os.path.exists(path):
                    os.makedirs(path)
                p = os.path.join(path, f"udf_{id}_memory.txt")

                with open(p, "w+") as f:
                    MemoryProfiler._show_results(cm, stream=f)

        if id is not None:
            dump(id)
        else:
            for id in sorted(code_map.keys()):
                dump(id)


class AccumulatorProfilerCollector(ProfilerCollector):
    def __init__(self) -> None:
        super().__init__()
        if SpecialAccumulatorIds.SQL_UDF_PROFIER in _accumulatorRegistry:
            self._accumulator = _accumulatorRegistry[SpecialAccumulatorIds.SQL_UDF_PROFIER]
        else:
            self._accumulator = Accumulator(
                SpecialAccumulatorIds.SQL_UDF_PROFIER, None, ProfileResultsParam
            )

    @property
    def _profile_results(self) -> "ProfileResults":
        with self._lock:
            value = self._accumulator.value
            return value if value is not None else {}
