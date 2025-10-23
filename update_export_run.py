# -*- coding: utf-8 -*-
from pathlib import Path
import os

path = Path("prod_core/persist/export_run.py")
text = path.read_text(encoding="utf-8")
text = text.replace("from collections import defaultdict\nfrom pathlib import Path\n", "from collections import defaultdict\nfrom pathlib import Path\nimport os\n")
path.write_text(text, encoding="utf-8")
