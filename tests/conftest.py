import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)  # tests read reagents.yaml from the repo root
sys.path.insert(0, ROOT)
