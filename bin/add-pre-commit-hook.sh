#!/bin/sh

cat > .git/hooks/pre-commit << EOF
#!/bin/sh

echo 'Running mypy:'
mypy --config-file= smawg/ || exit 1
echo

# https://stackoverflow.com/questions/70680757
echo 'Checking if flake8-docstrings is installed:'
flake8 --version | grep -q 'flake8-docstrings' || exit 1
echo
echo 'Checking if flake8-quotes is installed:'
flake8 --version | grep -q 'flake8_quotes' || exit 1
echo

echo 'Running flake8:'
flake8 --config=setup.cfg smawg/ || exit 1
echo

echo 'Running all tests with unittest:'
python3 -m unittest discover smawg/tests/ || exit 1
EOF

chmod a+x .git/hooks/pre-commit
