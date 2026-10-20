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
"""Ethiopian calendar helpers for the MoH portal."""

from __future__ import annotations

from datetime import date

# Julian day number of the day before 1 Meskerem, year 1 of the Ethiopian era.
_ETHIOPIAN_EPOCH_OFFSET = 1723856


def gregorian_to_ethiopian(day: date) -> tuple[int, int, int]:
    """Convert a Gregorian date to an Ethiopian ``(year, month, day)``.

    Months run 1 (Meskerem) to 13 (Pagume, 5 or 6 days long).
    """
    shifted_month_flag = (14 - day.month) // 12
    shifted_year = day.year + 4800 - shifted_month_flag
    shifted_month = day.month + 12 * shifted_month_flag - 3
    julian_day = (
        day.day
        + (153 * shifted_month + 2) // 5
        + 365 * shifted_year
        + shifted_year // 4
        - shifted_year // 100
        + shifted_year // 400
        - 32045
    )
    offset = julian_day - _ETHIOPIAN_EPOCH_OFFSET
    remainder = offset % 1461
    day_of_year = remainder % 365 + 365 * (remainder // 1460)
    year = 4 * (offset // 1461) + remainder // 365 - remainder // 1460
    return year, day_of_year // 30 + 1, day_of_year % 30 + 1


def current_period_key(today: date) -> str:
    """The ``YYYYMM`` key of the Ethiopian month containing ``today``.

    Matches the period keys used by the monthly data (``201901`` is Meskerem
    2019). Pagume is month 13, which sorts after every regular month.
    """
    year, month, _ = gregorian_to_ethiopian(today)
    return f"{year}{month:02d}"
