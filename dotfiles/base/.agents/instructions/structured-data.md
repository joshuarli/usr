# Structured data

Use `jaq --from FORMAT` and `--to FORMAT` for XML, TOML, CSV, and TSV instead of a parser script; file extensions select the input format, and `--slurp` collects records into one array. XML nodes use `.t` for the tag, `.a` for attributes, and `.c` for children. CSV and TSV records are arrays, and a header is an ordinary first row. Each output array becomes one CSV or TSV row, TOML output needs an object at the root, and XML output uses jaq's XML node representation. Use `jaq --from yaml` and `--to yaml` for YAML.
