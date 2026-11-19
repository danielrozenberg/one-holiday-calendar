"""Religious holiday calendars built from python-holidays' calendar mixins."""

from holidays import groups
from holidays import holiday_base
from holidays.calendars import julian


class _Christian(holiday_base.HolidayBase, groups.ChristianHolidays):
    def __init__(self, *args, **kwargs) -> None:
        groups.ChristianHolidays.__init__(self)
        super().__init__(*args, **kwargs)

    def _populate_public_holidays(self) -> None:
        self._add_epiphany_day("Epiphany")
        self._add_ash_wednesday("Ash Wednesday")
        self._add_palm_sunday("Palm Sunday")
        self._add_holy_thursday("Maundy Thursday")
        self._add_good_friday("Good Friday")
        self._add_easter_sunday("Easter Sunday")
        self._add_easter_monday("Easter Monday")
        self._add_ascension_thursday("Ascension Day")
        self._add_pentecost("Pentecost")
        self._add_pentecost_monday("Whit Monday")
        self._add_assumption_of_mary_day("Assumption Day")
        self._add_all_saints_day("All Saints' Day")
        self._add_christmas_eve("Christmas Eve")
        self._add_christmas_day("Christmas Day")
        self._add_christmas_day_two("Boxing Day")


class _Orthodox(holiday_base.HolidayBase, groups.ChristianHolidays):
    def __init__(self, *args, **kwargs) -> None:
        groups.ChristianHolidays.__init__(self, julian.JULIAN_CALENDAR)
        super().__init__(*args, **kwargs)

    def _populate_public_holidays(self) -> None:
        self._add_christmas_eve("Orthodox Christmas Eve")
        self._add_christmas_day("Orthodox Christmas Day")
        self._add_epiphany_day("Orthodox Theophany")
        self._add_good_friday("Orthodox Good Friday")
        self._add_easter_sunday("Orthodox Easter Sunday")
        self._add_easter_monday("Orthodox Easter Monday")
        self._add_ascension_thursday("Orthodox Ascension Day")
        self._add_pentecost("Orthodox Pentecost")


class _Jewish(holiday_base.HolidayBase, groups.HebrewCalendarHolidays):
    def __init__(self, *args, **kwargs) -> None:
        groups.HebrewCalendarHolidays.__init__(self)
        super().__init__(*args, **kwargs)

    def _populate_public_holidays(self) -> None:
        self._add_rosh_hashanah("Rosh Hashanah", range(2))
        self._add_yom_kippur("Yom Kippur")
        self._add_sukkot("Sukkot")
        self._add_sukkot("Shemini Atzeret", 7)
        self._add_sukkot("Simchat Torah", 8)
        self._add_hanukkah("Hanukkah", range(8))
        self._add_purim("Purim")
        self._add_passover("Passover", range(8))
        self._add_lag_baomer("Lag BaOmer")
        self._add_shavuot("Shavuot")


class _Islamic(holiday_base.HolidayBase, groups.IslamicHolidays):
    estimated_label = "%s (estimated)"

    def __init__(self, *args, **kwargs) -> None:
        groups.IslamicHolidays.__init__(self)
        super().__init__(*args, **kwargs)

    def _populate_public_holidays(self) -> None:
        self._add_islamic_new_year_day("Islamic New Year")
        self._add_ashura_day("Ashura")
        self._add_mawlid_day("Mawlid")
        self._add_isra_and_miraj_day("Isra and Mi'raj")
        self._add_ramadan_beginning_day("Ramadan begins")
        self._add_laylat_al_qadr_day("Laylat al-Qadr")
        self._add_eid_al_fitr_day("Eid al-Fitr")
        self._add_arafah_day("Day of Arafah")
        self._add_eid_al_adha_day("Eid al-Adha")


class _Hindu(holiday_base.HolidayBase, groups.HinduCalendarHolidays):
    estimated_label = "%s (estimated)"

    def __init__(self, *args, **kwargs) -> None:
        groups.HinduCalendarHolidays.__init__(self)
        super().__init__(*args, **kwargs)

    def _populate_public_holidays(self) -> None:
        self._add_makar_sankranti("Makar Sankranti")
        self._add_maha_shivaratri("Maha Shivaratri")
        self._add_holi("Holi")
        self._add_raksha_bandhan("Raksha Bandhan")
        self._add_janmashtami("Janmashtami")
        self._add_ganesh_chaturthi("Ganesh Chaturthi")
        self._add_dussehra("Dussehra")
        self._add_diwali("Diwali")


RELIGIONS: dict[str, tuple[str, type[holiday_base.HolidayBase]]] = {
    "christian": ("Christian", _Christian),
    "orthodox": ("Orthodox Christian", _Orthodox),
    "jewish": ("Jewish", _Jewish),
    "islamic": ("Islamic", _Islamic),
    "hindu": ("Hindu", _Hindu),
}
