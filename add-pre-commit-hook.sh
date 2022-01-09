#!/bin/sh

cat > .git/hooks/pre-commit << EOF
#!/bin/sh

echo 'Running mypy:'
mypy --config-file= . || exit 1
echo

echo 'Running flake8:'
flake8 --isolated . || exit 1
echo

echo 'Running all tests with unittest:'
python3 -m unittest discover || exit 1
EOF

chmod a+x .git/hooks/pre-commit
