#!/bin/sh

cat > .git/hooks/pre-commit << EOF
#!/bin/sh

echo 'Running mypy:'
mypy . || exit 1
echo

echo 'Running flake8:'
flake8 . || exit 1
EOF

chmod a+x .git/hooks/pre-commit
