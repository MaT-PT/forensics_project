import os
import pytest
from sleuthlib.utils import *

class TestUtils:

    def populate_tmp_dir(self, tmp_path):
        for applet in REQUIRED_TOOLS:
            with open(os.path.join(tmp_path, applet), "w") as fd:
                fd.write(applet)         

    def test_all(self, tmp_path, tmp_path2):

        self.populate_tmp_dir(tmp_path)

        set_tsk_path(tmp_path)
        assert get_program_path("mmls") == os.path.join(tmp_path, "mmls")
        assert get_program_path("fls") == os.path.join(tmp_path, "fls")
        assert get_program_path("icat") == os.path.join(tmp_path, "icat")

        set_tsk_path(tmp_path2)
        with pytest.raises(FileNotFoundError) as excinfo:
            check_required_tools()
        
        assert tmp_path2 in str(excinfo)

