#!/usr/bin/env python
# -*- coding: utf-8 -*-
# ****************************************
#                              __
#   _________  ____ ___  ___  / /__  __
#  / ___/ __ \/ __ `__ \/ _ \/ __/ |/_/
# / /__/ /_/ / / / / / /  __/ /__>  <
# \___/\____/_/ /_/ /_/\___/\__/_/|_|
#
#
#  Copyright (c) 2023 Cometx Development
#      Team. All rights reserved.
# ****************************************
"""
To upload experiment data to new experiments.

cometx upload WORKSPACE SOURCE-FOLDER
cometx upload WORKSPACE/PROJECT SOURCE-FOLDER


| Destination:       | WORKSPACE            | WORKSPACE/PROJECT      |
| Source (below)     |                      |                        |
|--------------------|----------------------|------------------------|
| WORKSPACE/*/*      | Copies all projects  | N/A                    |
| WORKSPACE/PROJ/*   | N/A                  | Copies all experiments |
| WORKSPACE/PROJ/EXP | N/A                  | Copies experiment      |
"""

import argparse
import glob
import json
import os
import sys

from comet_ml import Experiment, API
from comet_ml.messages import StandardOutputMessage, InstalledPackagesMessage, HtmlMessage

from cometx.utils import get_file_extension


ADDITIONAL_ARGS = False

# From filename extension to Comet Asset Type
EXTENSION_MAP = {
    "asset": "asset",
    "datagrid": "datagrid",
    "png": "image",
    "jpg": "image",
    "gif": "image",
    "txt": "text-sample",
    "webm": "video",
    "mp4": "video",
    "ogg": "video",
    "ipynb": "notebook",
    "wav": "audio",
    "mp3": "audio",
    #    "curve": "curve", FIXME: add
}
# Fom CLI type to Comet Asset Type
# List only those that differ from
# type.lower() != Comet Asset Type
TYPE_MAP = {
    "text": "text-sample",
}

def get_parser_arguments(parser):
    parser.add_argument(
        "COMET_DESTINATION",
        help=(
            "The Comet destination: 'WORKSPACE', 'WORKSPACE/PROJECT'"
        ),
        type=str,
    )
    parser.add_argument(
        "COMET_SOURCE",
        help=(
            "The folder containing the experiments to upload: 'workspace/*/*', or 'workspace/project/*' or 'workspace/project/experiment'"
        ),
        type=str,
    )
    parser.add_argument(
        "--debug",
        help="If given, allow debugging",
        default=False,
        action="store_true"
    )


def upload(parsed_args, remaining=None):
    # Called via `cometx upload ...`
    try:
        upload_cli(parsed_args)
    except KeyboardInterrupt:
        print("Canceled by CONTROL+C")
    except Exception as exc:
        if parsed_args.debug:
            raise
        else:
            print("ERROR: " + str(exc))

def create_experiment(workspace_dst, project_dst):
    """
    Create an experiment in destination workspace
    and project, and return a APIExperiment.
    """
    experiment = Experiment(
        project_name=project_dst,
        workspace=workspace_dst,
        log_code=False,
        log_graph=False,
        auto_param_logging=False,
        auto_metric_logging=False,
        parse_args=False,
        auto_output_logging="simple",
        log_env_details=False,
        log_git_metadata=False,
        log_git_patch=False,
        disabled=False,
        log_env_gpu=False,
        log_env_host=False,
        display_summary=None,
        log_env_cpu=False,
        log_env_network=False,
        display_summary_level=1,
        optimizer_data=None,
        auto_weight_logging=None,
        auto_log_co2=False,
        auto_metric_step_rate=10,
        auto_histogram_tensorboard_logging=False,
        auto_histogram_epoch_rate=1,
        auto_histogram_weight_logging=False,
        auto_histogram_gradient_logging=False,
        auto_histogram_activation_logging=False,
        experiment_key=None,
    )
    return experiment


def get_experiment_folders(workspace_src, project_src, experiment_src):
    yield from glob.iglob(f"{workspace_src}/{project_src}/{experiment_src}")

def copy_experiment_to(experiment_folder, workspace_dst, project_dst):
    # if project doesn't exist, create it
    experiment = create_experiment(workspace_dst, project_dst)
    # copy experiment_folder stuff to experiment
    # copy all resources to existing or new experiment
    log_all(experiment, experiment_folder)
    experiment.end()

def upload_cli(parsed_args):
    """
    | Destination:       | WORKSPACE            | WORKSPACE/PROJECT      |
    | Source (below)     |                      |                        |
    |--------------------|----------------------|------------------------|
    | WORKSPACE/*/*      | Copies all projects  | N/A                    |
    | WORKSPACE/PROJ/*   | N/A                  | Copies all experiments |
    | WORKSPACE/PROJ/EXP | N/A                  | Copies experiment      |
    """
    api = API()

    comet_destination = (
        parsed_args.COMET_DESTINATION.split("/") if parsed_args.COMET_DESTINATION is not None else []
    )

    if len(comet_destination) == 1:
        workspace_dst = comet_destination[0]
        project_dst = None
    elif len(comet_destination) == 2:
        workspace_dst, project_dst = comet_destination
    else:
        raise Exception("invalid COMET_DESTINATION: %r" % parsed_args.COMET_DESTINATION)

    comet_source = (
        parsed_args.COMET_SOURCE.split("/") if parsed_args.COMET_SOURCE is not None else []
    )

    if len(comet_source) == 3:
        workspace_src, project_src, experiment_src = comet_source
    else:
        raise Exception("invalid COMET_SOURCE: %r" % parsed_args.COMET_SOURCE)

    for experiment_folder in get_experiment_folders(workspace_src, project_src, experiment_src):
        copy_experiment_to(experiment_folder, workspace_dst, project_dst)

    return


def get_filenames(path):
    for filename in glob.glob(path):
        if os.path.isfile(filename):
            yield filename
        else:
            for entry in os.scandir(filename):
                if entry.is_dir(follow_symlinks=False):
                    yield from get_filenames(entry.path)
                else:
                    yield entry.path
            
def log_experiment_assets_from_file(experiment, filename, file_type):
    SKELETON = filename
    for filename in get_filenames(SKELETON):
        if not file_type:
            extension = get_file_extension(filename)
            file_type = EXTENSION_MAP.get(extension.lower(), "asset")

        if file_type == "notebook":
            # metadata = FIXME: get metadata dict from args
            experiment.log_notebook(filename)
            #elif file_type == "histogram":
            # decompose, re-log it
            #elif file_type == "confusion-matrix":
            # TODO: what to do about assets referenced in matrix?
            #elif file_type == "embedding":
            # TODO: what to do about assets referenced in embedding?
        else:
            # metadata = FIXME: get metadata dict from args
            binary_io = open(filename, "rb")

            experiment._log_asset(
                binary_io,
                file_name=filename.split("/", 5)[-1],
                copy_to_tmp=True,
                asset_type=file_type,
            )

def log_experiment_code_from_file(experiment, filename):
    """
    """
    if os.path.exists(filename):
        if os.path.isfile(filename):
            experiment.log_code(str(filename))
        elif os.path.isdir(filename):
            experiment.log_code(folder=str(filename))

def log_experiment_requirements_from_file(experiment, filename):
    """
    Requirements (pip packages)
    """
    if os.path.exists(filename):
        installed_packages_list = [package for package in open(filename)]
        if installed_packages_list is None:
            return
        message = InstalledPackagesMessage.create(
            context=experiment.context,
            use_http_messages=experiment.streamer.use_http_messages,
            installed_packages=installed_packages_list,
        )
        experiment._enqueue_message(message)

def log_experiment_metrics_from_file(experiment, filename):
    """
    """
    if os.path.exists(filename):
        for line in open(filename):
            dict_line = json.loads(line)
            name = dict_line["metricName"]
            value = dict_line["metricValue"]
            step = dict_line["step"]
            epoch = dict_line["epoch"]
            # FIXME: does not log time, duration
            experiment.log_metric(name, value, step=step, epoch=epoch)

def log_experiment_parameters_from_file(experiment, filename):
    """
    """
    if os.path.exists(filename):
        parameters = json.load(open(filename))
        for parameter in parameters:
            name = parameter["name"]
            value = parameter["valueCurrent"]
            experiment.log_parameter(name, value)

def log_experiment_others_from_file(experiment, filename):
    """
    """
    if os.path.exists(filename):
        for line in open(filename):
            dict_line = json.loads(line)
            name = dict_line["name"]
            value = dict_line["valueCurrent"]
            experiment.log_other(key=name, value=value)

def log_experiment_output(experiment, output_file):
    """
    """
    if os.path.exists(output_file):
        for line in open(output_file):
            message = StandardOutputMessage.create(
                context=experiment.context,
                use_http_messages=experiment.streamer.use_http_messages,
                output=line,
                stderr=False,
            )
            experiment._enqueue_message(message)

def log_experiment_html(experiment, filename):
    if os.path.exists(filename):
        html = open(filename).read()
        message = HtmlMessage.create(
            context=self.context,
            use_http_messages=self.streamer.use_http_messages,
            html=html,
        )
        experiment._enqueue_message(message)

def log_all(experiment, experiment_folder):
    """
    """
    log_experiment_metrics_from_file(
        experiment,
        os.path.join(experiment_folder, "metrics.jsonl")
    )

    log_experiment_parameters_from_file(
        experiment,
        os.path.join(experiment_folder, "parameters.json")
    )

    log_experiment_others_from_file(
        experiment,
        os.path.join(experiment_folder, "others.jsonl")
    )

    for dirname in glob.glob(os.path.join(experiment_folder, "assets", "*")):
        if os.path.isdir(dirname):
            base, asset_type = dirname.rsplit("/", 1)
            log_experiment_assets_from_file(
                experiment,
                os.path.join(experiment_folder, "assets", asset_type, "*"),
                asset_type
            )

    log_experiment_output(
        experiment,
        os.path.join(experiment_folder, "run/output.txt")
    )

    log_experiment_requirements_from_file(
        experiment, 
        os.path.join(experiment_folder, "run/requirements.txt")
    )


    
    # FIXME:
    ## models
    ## notes
    ## metadata
    ## confusion-matrix assets
    ## histogram (deconstruct) and assets
    ## html

def main(args):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    get_parser_arguments(parser)
    parsed_args = parser.parse_args(args)
    upload(parsed_args)


if __name__ == "__main__":
    # Called via `python -m cometx.cli.upload ...`
    main(sys.argv[1:])
