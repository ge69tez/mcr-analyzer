xvfb-run python3 -m scalene --no-browser --program-path src --cli --reduced-profile --- -m pytest --no-cov -k test_profile || true # cSpell:ignore xvfb
