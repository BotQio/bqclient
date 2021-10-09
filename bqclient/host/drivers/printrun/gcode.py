from typing import Union, Optional


class GCodeLine(object):
    def __init__(self, line: str):
        line = line.rstrip('\n')
        self._line = line

        self._mapping = {}
        self._comment = None

        if line and line[0].isalpha():
            self._type = line[0].upper()
        else:
            self._type = None

        while line:
            first_character = line[0]
            if first_character == ' ':
                line = line[1:]
            elif first_character.isalpha():
                end_index = 1
                while end_index < len(line) and line[end_index] in '0123456789.-':
                    end_index += 1
                value_str = line[1:end_index]

                key = first_character.upper()
                if '.' in value_str:
                    self._mapping[key] = float(value_str)
                else:
                    self._mapping[key] = int(value_str)
                line = line[end_index:]
            elif first_character == ';':  # Comment
                test_index = 1
                while test_index < len(line) and line[test_index] == " ":
                    test_index += 1

                self._comment = line[test_index:]
                line = ""

    def __contains__(self, key) -> bool:
        return key in self._mapping

    def __getitem__(self, key) -> Optional[Union[float, int, str]]:
        return self._mapping[key]

    def keys(self):
        return self._mapping.keys()

    @property
    def type(self) -> Optional[str]:
        return self._type

    @property
    def comment(self) -> Optional[str]:
        return self._comment

    @property
    def uncommented(self) -> str:
        if self.comment is None:
            return self._line
        return self._line[0:len(self._line) - len(self.comment)].rstrip(' ;')

