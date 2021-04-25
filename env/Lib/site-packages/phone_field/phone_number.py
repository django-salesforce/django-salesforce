import re


PHONE_TEST_REGEX = re.compile(r'^\+?1?-?\s*'         # optional leading '+1-' and whitespace
                              r'\(?([2-9]\d{2})\)?'  # extract first three digits (0/1 first digit is international)
                              r'[-\.\s]*'            # strip -, ., and whitespace
                              r'(\d{3})'             # next three digits
                              r'[-\.\s]*'            # strip -, ., and whitespace
                              r'(\d{4})$')           # last four digits

BACKEND_EXTENSION_SEPARATOR = 'x'
VALID_EXTENSION_SEPARATOR = ', press '


class PhoneNumber:
    def __init__(self, txt):
        self.raw_phone = str(txt) if txt else ''
        self._is_parsed = False
        self._base_number = ''
        self._base_number_dirty = ''
        self._extensions = []
        self._has_extensions = False
        self._valid_extensions = False
        self._is_number_E164 = False
        self._cleaned = ''

    def parse(self):
        if not self._is_parsed and self.raw_phone:
            if VALID_EXTENSION_SEPARATOR in self.raw_phone:
                parts = self.raw_phone.split(VALID_EXTENSION_SEPARATOR)
            else:
                parts = self.raw_phone.split(BACKEND_EXTENSION_SEPARATOR)

            self._base_number = self._base_number_dirty = parts[0].strip()
            self._extensions = [x.strip() for x in parts[1:]]

            # Clean base phone number. Currently only accepts US phone numbers as E164. Processing international
            # numbers will require more logic (e.g. making sure first digits are a country code, removing "0" prefix
            # from some local numbers, etc.).
            self._is_number_E164 = False
            regex_test = PHONE_TEST_REGEX.search(self._base_number)
            if regex_test:
                self._is_number_E164 = True
                self._base_number = '+1' + ''.join(regex_test.groups())
            self._cleaned = self._base_number

            # Clean extensions. Valid extensions are only digits and are separated by 'x'.
            self._valid_extensions = True
            self._has_extensions = bool(self._extensions)
            for extension in self._extensions:
                if not extension.isdigit():
                    self._valid_extensions = False
                    break
            if self._extensions:
                self._cleaned += BACKEND_EXTENSION_SEPARATOR + BACKEND_EXTENSION_SEPARATOR.join(self._extensions)
            self._is_parsed = True

    @property
    def is_E164(self):
        # Whether the phone number can be expressed with the E164 standard (no extensions allowed).
        # E.g (415) 222-3333    ->      +14152223333
        # E.g. 44 020 7183 8750 ->      +442071838750
        # Currently, PhoneField only recognizes the first case/US phone numbers as E164.
        self.parse()
        return self._is_number_E164 and not self._has_extensions

    @property
    def is_standard(self):
        # Whether the base number is E164, but also has valid extensions (E164 does not allow extensions)
        self.parse()
        return self._is_number_E164 and self._valid_extensions

    @property
    def is_usa(self):
        # Whether this is an E164 phone number (see above) with a US country code
        self.parse()
        return self._is_number_E164 and self._cleaned.startswith('+1')

    @property
    def cleaned(self):
        # Canonically formatted value, as in "+12223334444x55". This is what's stored in the DB.
        self.parse()
        return self._cleaned

    @property
    def base_number(self, clean=True):
        # The base part of the cleaned number, e.g. "+12223334444".
        self.parse()
        return self._base_number if clean else self._base_number_dirty

    @property
    def base_number_fmt(self):
        # The base part of the cleaned number, but formatted: e.g. "(415) 222-3333"
        if self.is_usa:
            return '({}) {}-{}'.format(self._base_number[2:5], self._base_number[5:8], self._base_number[8:12])
        return self._base_number

    @property
    def extensions(self):
        self.parse()
        return self._extensions

    @property
    def formatted(self):
        val = self.base_number_fmt
        if self._valid_extensions:
            for ext in self._extensions:
                val += VALID_EXTENSION_SEPARATOR + str(ext)
        elif self._has_extensions:
            val += BACKEND_EXTENSION_SEPARATOR + BACKEND_EXTENSION_SEPARATOR.join(self._extensions)
        return val

    def __str__(self):
        return self.formatted

    def __len__(self):
        return len(self.cleaned)

    def __bool__(self):
        return bool(self.cleaned)

    def __hash__(self):
        return hash(self.cleaned)

    def __eq__(self, ph):
        if isinstance(ph, PhoneNumber):
            return self.cleaned == ph.cleaned
        elif isinstance(ph, str):
            return self.cleaned == PhoneNumber(ph).cleaned
        elif not ph and not self:
            return True
        return False
