# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
from datetime import date

import pytest

from superset.moh_calendar import current_period_key, gregorian_to_ethiopian


@pytest.mark.parametrize(
    ("gregorian", "ethiopian"),
    [
        (date(2026, 9, 11), (2019, 1, 1)),
        (date(2026, 9, 21), (2019, 1, 11)),
        (date(2026, 9, 10), (2018, 13, 5)),
        (date(2026, 7, 8), (2018, 11, 1)),
        (date(2024, 9, 11), (2017, 1, 1)),
        (date(2023, 9, 12), (2016, 1, 1)),
        # The year before an Ethiopian leap year has a six-day Pagume.
        (date(2023, 9, 11), (2015, 13, 6)),
    ],
)
def test_gregorian_to_ethiopian(
    gregorian: date, ethiopian: tuple[int, int, int]
) -> None:
    assert gregorian_to_ethiopian(gregorian) == ethiopian


def test_current_period_key_matches_monthly_period_keys() -> None:
    assert current_period_key(date(2026, 9, 21)) == "201901"
    assert current_period_key(date(2026, 8, 8)) == "201812"
    assert current_period_key(date(2026, 9, 10)) == "201813"
