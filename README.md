# cometx

```
   _________  ____ ___  ___  / /__  __
  / ___/ __ \/ __ `__ \/ _ \/ __/ |/_/
 / /__/ /_/ / / / / / /  __/ /__>  <
 \___/\____/_/ /_/ /_/\___/\__/_/|_|
```

Open source extensions for the [Comet](https://www.comet.com/site/?utm_source=cometx&utm_medium=referral&utm_campaign=cometx_2022&utm_content=github) SDK.

These extensions are created and supported by the community and are
not an official project of Comet ML. We welcome contributions!

## Installation

```
pip install git+https://github.com/comet-ml/comet-sdk-extensions.git#egg=cometx
```

To use these command-line functions, you'll need to have your Comet
API key set in one of the following two ways.

1. [Environment variables](https://www.comet.com/docs/v2/guides/tracking-ml-training/configuring-comet/?utm_source=cometx&utm_medium=referral&utm_campaign=cometx_2022&utm_content=github#configure-comet-through-environment-variables)
2. [Comet config file](https://www.comet.com/docs/v2/guides/tracking-ml-training/configuring-comet/?utm_source=cometx&utm_medium=referral&utm_campaign=cometx_2022&utm_content=github#configure-comet-using-the-comet-config-file)

Either this way:

```
export COMET_API_KEY="YOUR-COMET-API-KEY"
```

or this way:

```
[comet]
api_key = YOUR-COMET-API-KEY
```

If you are an Comet on-prem user, you'll also need to set the
`COMET_URL_OVERRIDE` environment variable, or add it to your
`~/.comet.config` file as below:

Either this way:

```
export COMET_API_KEY="YOUR-COMET-API-KEY"
export COMET_URL_OVERRIDE="https://your-companys-comet.com/clientlib/"
```

or this way:

```
[comet]
api_key = YOUR-COMET-API-KEY
url_override = https://your-companys-comet.com/clientlib/
```

## Usage

The subcommands:

* cometx list
* cometx download
* cometx copy
* cometx log
* cometx reproduce
* cometx delete-assets

### cometx list

This command is used to:

* get a list of all workspaces that you are a member of
* get a list of all projects in a workspace
* get a list of all experiments (by name or key) in a project

cometx list examples:

```
cometx list WORKSPACE/PROJECT/EXPERIMENT-KEY-OR-NAME
cometx list WORKSPACE/PROJECT
cometx list WORKSPACE
cometx list
```

### cometx copy

This command is used to:

* copy downloaded data to a new experiment
* create a symlink from one project to existing experiments

cometx copy examples:

```
cometx SOURCE DESTINATION
cometx --symlink SOURCE DESTINATION
```

where SOURCE is:

* if not `--symlink`, "WORKSPACE/PROJECT/EXPERIMENT", "WORKSPACE/PROJECT/*", or "WORKSPACE/*/*" folder (use quotes)
* if `--symlink`, then it is a Comet path to workspace or workspace/project

where DESTINATION is:

* WORKSPACE
* WORKSPACE/PROJECT

Not all combinations are possible:


| Destination:<br/>Source (below)| WORKSPACE            | WORKSPACE/PROJECT      |
|--------------------|----------------------|------------------------|
| `WORKSPACE/*/*`      | Copies all projects  | N/A                    |
| `WORKSPACE/PROJ/*`   | N/A                  | Copies all experiments |
| `WORKSPACE/PROJ/EXP` | N/A                  | Copies experiment      |


### cometx download

This command is used to:

* download all workspaces, projects, and experiments of workspaces that you are a member of
* download all projects, and experiments of a given workspace
* download all experiments of a given workspace/project

cometx dowload examples:

```
cometx download WORKSPACE/PROJECT/EXPERIMENT-KEY-OR-NAME [RESOURCE ...] [FLAGS ...]
cometx download WORKSPACE/PROJECT [RESOURCE ...] [FLAGS ...]
cometx download WORKSPACE [RESOURCE ...] [FLAGS ...]
cometx download [RESOURCE ...] [FLAGS ...]
```

Where [RESOURCE ...] is zero or more of the following names:

* assets
* html
* metadata
* metrics
* others
* parameters
* project - alias for: project_notes, project_metadata
* run - alias for: code, git, output, graph, and requirements
* system

If no RESOURCE is given it will download all of them.

Where [FLAGS ...] is zero or more of the following:

* `--list` - use to list available workspaces, projects, experiments,
    artifacts, or models (same as `cometx list`)
* `--output` - download resources to folder other than current one
* `--flat` - don't use the normal hiearchy for downloaded items
* `--use-name` - use experiment names for folders and listings
* `--ignore` - don't download the following resources (use one or more
    RESOURCE names from above)
* `--asset-type` - asset type to match, or leave off to match all
* `--filename` - filename to match, or leave off to match all
* `--overwrite` - overwrite any existing files
* `--force` - don't ask to download, just do it
* `--help` - this message

To download artifacts:

```
cometx download WORKSPACE/artifacts/NAME [FLAGS ...]
cometx download WORKSPACE/artifacts/NAME/VERSION-OR-ALIAS [FLAGS ...]
```

To download models from the model registry:

```
cometx download WORKSPACE/model-registry/NAME [FLAGS ...]
cometx download WORKSPACE/model-registry/NAME/VERSION-OR-STAGE [FLAGS ...]
```

### cometx log

This command is used to log a file to a specific experiment.

cometx log example:

```
cometx log WORKSPACE/PROJECT/EXPERIMENT-KEY-OR-NAME [--type TYPE] FILENAME.EXT
```

where TYPE is the asset type of the filename. TYPE is not needed if the
filename extension (FILENAME.EXT) is known.

Known extensions:

* png
* jpg
* gif
* txt
* webm
* mp4
* ogg
* ipynb
* wav
* mp3

Known types:

* asset
* image
* text-sample
* video
* ipynb
* audio

Example to set an other key:value:

```
cometx log WORKSPACE/PROJECT --type other --set "key:value"
cometx log WORKSPACE/PROJECT/EXPERIMENT-KEY-OR-NAME --type other --set "key:value"
```
The first version will set the other key:value in all experiments in a project, and the second will set the other key:value in the experiment.


Example to log all items:

```
cometx log WORKSPACE/PROJECT PATH-TO-DOWNLOAD --type all
cometx log WORKSPACE/PROJECT/EXPERIMENT-KEY-OR-NAME PATH-TO-DOWNLOAD --type all
```
The first version will create an experiment, and the second will log everything to an existing experiment.

### cometx delete-assets

To delete experiments assets:

```
cometx delete-assets WORKSPACE/PROJECT --type=image
cometx delete-assets WORKSPACE/PROJECT/EXPERIMENT --type=all
```
Type can be valid asset tupe, including:

* all
* asset
* audio
* code
* image
* notebook
* text-sample
* video

### cometx reproduce

```
cometx reproduce [-h] [--run] [--executable EXECUTABLE] COMET_PATH OUTPUT_DIR
```

For all variations, use the `--help` flag to get additional information.

## Running Tests

WARNING: Running the tests will create experiments, models, assets, etc.
in your default workspace if not set otherwise.

To run the tests, you can either export all of these items in the
environment:

```shell
$ export COMET_USER="<USERNAME>"
$ export COMET_WORKSPACE="<WORKSPACE>"
$ export COMET_API_KEY="<API-KEY>"
$ pytest tests
```

Or, define `workspace` and `api_key` in your ~/.comet.config file:

```shell
$ export COMET_USER="<USERNAME>"
$ pytest tests
```
