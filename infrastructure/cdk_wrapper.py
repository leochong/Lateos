#!/usr/bin/env python3
"""
CDK App Wrapper

Workaround for JSII constructs._jsii import issue.
Pre-loads the constructs module before executing the main app.
"""

import os
import sys

# Pre-load constructs._jsii to avoid circular dependency issues
import constructs._jsii  # noqa: F401

# Ensure we can import from the infrastructure directory
sys.path.insert(0, os.path.dirname(__file__))

# Import and run the app
from app import app  # noqa: E402

# Synth the app
app.synth()
