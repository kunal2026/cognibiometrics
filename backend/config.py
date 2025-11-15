# config.py - configuration for web-based cognitive biometric prototype

BASELINE_SECONDS = 60           # seconds to learn baseline
ANALYSIS_INTERVAL = 5           # how often to recompute state
WINDOW_SECONDS = 60             # rolling window for features
BURNOUT_HISTORY_POINTS = 60     # number of history points to store
TRUST_MAX_DISTANCE = 200.0      # scaling for trust score distance

DEBUG_LOG = True
