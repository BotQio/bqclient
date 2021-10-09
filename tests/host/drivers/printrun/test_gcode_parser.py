import string

from bqclient.host.drivers.printrun.gcode import GCodeLine


class TestGcodeParser(object):
    def test_empty_line(self):
        line = GCodeLine("")

        for letter in string.ascii_uppercase:
            assert letter not in line

        assert line.comment is None

    def test_single_element_gcode_command(self):
        line = GCodeLine("G21")

        assert line.type == 'G'
        assert 'G' in line
        assert line['G'] == 21
        assert line.uncommented == "G21"

    def test_multiple_floats_command(self):
        line = GCodeLine("G0 X1.1 Y2.2 Z3.3 E-5.0")

        assert line.type == 'G'
        assert 'G' in line
        assert line['G'] == 0
        assert 'X' in line
        assert line['X'] == 1.1
        assert 'Y' in line
        assert line['Y'] == 2.2
        assert 'Z' in line
        assert line['Z'] == 3.3
        assert 'E' in line
        assert line['E'] == -5.0
        assert line.uncommented == "G0 X1.1 Y2.2 Z3.3 E-5.0"

    def test_floats_and_ints_command(self):
        line = GCodeLine("G0 X1 Y2.0")

        assert line.type == 'G'
        assert 'G' in line
        assert line['G'] == 0
        assert 'X' in line
        assert line['X'] == 1
        assert 'Y' in line
        assert line['Y'] == 2.0

    def test_lowercase_letters(self):
        line = GCodeLine("g0 x1 y2.0")

        assert line.type == 'G'
        assert 'G' in line
        assert line['G'] == 0
        assert 'X' in line
        assert line['X'] == 1
        assert 'Y' in line
        assert line['Y'] == 2.0

    def test_reading_comments_at_end_of_line(self):
        line = GCodeLine("G28 ; Home the machine")

        assert line.type == 'G'
        assert 'G' in line
        assert line['G'] == 28
        assert line.comment == "Home the machine"
        assert line.uncommented == "G28"

    def test_reading_empty_comment(self):
        line = GCodeLine(";")

        assert line.type is None
        assert line.comment == ""
        assert line.uncommented == ""

    def test_reading_comment_with_only_spaces(self):
        line = GCodeLine("G28 ;       ")

        assert line.type == 'G'
        assert line.comment == ""
        assert line.uncommented == "G28"

    def test_reading_only_comment(self):
        line = GCodeLine(";WIPE_START")

        assert line.type is None
        assert line.comment == 'WIPE_START'
        assert line.uncommented == ""
