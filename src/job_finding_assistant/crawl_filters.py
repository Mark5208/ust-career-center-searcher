"""Crawl Filters — Job Board search criteria applied during a Crawl."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class CrawlFilters:
    """User-chosen Job Board criteria plus optional Deadline Hardline.

    Default is Active Job on, other filters empty, Hardline unset.
    """

    business_natures: tuple[str, ...] = ()
    job_natures: tuple[str, ...] = ()
    employment_types: tuple[str, ...] = ()
    working_locations: tuple[str, ...] = ()
    levels_of_qualification: tuple[str, ...] = ()
    employment_modes: tuple[str, ...] = ()
    languages: tuple[str, ...] = ()
    talent_wise_employment_charter: bool = False
    active_job: bool = True
    non_chinese_speaking_students: bool = False
    deadline_hardline: date | None = None

    def is_closing_capable(self) -> bool:
        """True when unfiltered or Active-Job-only (may mark absent postings Closed)."""
        has_group_filters = any(
            (
                self.business_natures,
                self.job_natures,
                self.employment_types,
                self.working_locations,
                self.levels_of_qualification,
                self.employment_modes,
                self.languages,
            )
        )
        has_extra_checkboxes = (
            self.talent_wise_employment_charter or self.non_chinese_speaking_students
        )
        return not has_group_filters and not has_extra_checkboxes
