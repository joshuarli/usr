#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "tools" / "close-stale-prs" / "src"))
from close_stale_prs import main

sys.exit(main())
