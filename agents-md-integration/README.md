# Integrate your AGENTS.md, SKILL.md and other Instructions with Dynatrace

![notebook](assets/notebook.png)

`AGENTS.md`, `SKILL.md` and other similar Markdown files are crucial ways to guide your agents, so understanding what files you have and how they can influence your agent's behaviour is crucial.

The Dynatrace workflow in this directory runs periodically, grabs the contents of any file (the workflow uses `AGENTS.md` as an example but you can use it to retrieve any file) then appends the content of that file to a Dynatrace notebook.

The workflow can be expanded to retrieve as many files as you wish.

The dashboard shows not only the contents of each file, it also provides a link to the precise Git commit at the time it was retrieved - in case of changes or issues, you can see exactly what changed and when.

## Getting Started

1. Download the workflow template YAML file
2. In Dynatrace, press `ctrl + k` and search for notebooks
