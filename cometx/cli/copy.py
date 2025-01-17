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
To copy experiment data to new experiments.

cometx copy [--symlink] SOURCE DESTINATION

where SOURCE is:

* if not --symlink, "WORKSPACE/PROJECT/EXPERIMENT", "WORKSPACE/PROJECT", or "WORKSPACE" folder
* if --symlink, then it is a Comet path to workspace or workspace/project

where DESTINATION is:

* WORKSPACE
* WORKSPACE/PROJECT

Not all combinations are possible:


| Destination:       | WORKSPACE            | WORKSPACE/PROJECT      |
| Source (below)     |                      |                        |
|--------------------|----------------------|------------------------|
| WORKSPACE          | Copies all projects  | N/A                    |
| WORKSPACE/PROJ     | N/A                  | Copies all experiments |
| WORKSPACE/PROJ/EXP | N/A                  | Copies experiment      |
"""

import argparse
import glob
import json
import os
import sys

from comet_ml import API, APIExperiment, Artifact, Experiment, OfflineExperiment
from comet_ml._typing import TemporaryFilePath
from comet_ml.connection import compress_git_patch
from comet_ml.file_uploader import GitPatchUploadProcessor
from comet_ml.messages import (
    GitMetadataMessage,
    HtmlMessage,
    InstalledPackagesMessage,
    MetricMessage,
    StandardOutputMessage,
    SystemDetailsMessage,
)

from ..utils import remove_extra_slashes
from .copy_utils import upload_single_offline_experiment

ADDITIONAL_ARGS = False


def get_parser_arguments(parser):
    parser.add_argument(
        "COMET_SOURCE",
        help=(
            "The folder containing the experiments to copy: 'workspace', or 'workspace/project' or 'workspace/project/experiment'"
        ),
        type=str,
    )
    parser.add_argument(
        "COMET_DESTINATION",
        help=("The Comet destination: 'WORKSPACE', 'WORKSPACE/PROJECT'"),
        type=str,
    )
    parser.add_argument(
        "-i",
        "--ignore",
        help="Resource(s) (or 'experiments') to ignore.",
        nargs="+",
        default=[],
    )
    parser.add_argument(
        "--debug", help="If given, allow debugging", default=False, action="store_true"
    )
    parser.add_argument(
        "--quiet",
        help="If given, don't display update info",
        default=False,
        action="store_true",
    )
    parser.add_argument(
        "--symlink",
        help="Instead of copying, create a link to an experiment in a project",
        default=False,
        action="store_true",
    )


def copy(parsed_args, remaining=None):
    # Called via `cometx copy ...`
    try:
        copy_manager = CopyManager()
        copy_manager.copy(
            parsed_args.COMET_SOURCE,
            parsed_args.COMET_DESTINATION,
            parsed_args.symlink,
            parsed_args.ignore,
            parsed_args.debug,
            parsed_args.quiet,
        )
        if parsed_args.debug:
            print("finishing...")

    except KeyboardInterrupt:
        if parsed_args.debug:
            raise
        else:
            print("Canceled by CONTROL+C")
    except Exception as exc:
        if parsed_args.debug:
            raise
        else:
            print("ERROR: " + str(exc))


class CopyManager:
    def __init__(self):
        """
        | Destination:       | WORKSPACE            | WORKSPACE/PROJECT      |
        | Source (below)     |                      |                        |
        |--------------------|----------------------|------------------------|
        | WORKSPACE          | Copies all projects  | N/A                    |
        | WORKSPACE/PROJ     | N/A                  | Copies all experiments |
        | WORKSPACE/PROJ/EXP | N/A                  | Copies experiment      |
        """
        self.api = API()

    def copy(self, source, destination, symlink, ignore, debug, quiet):
        """ """
        self.ignore = ignore
        self.debug = debug
        self.quiet = quiet
        self.copied_reports = False
        comet_destination = remove_extra_slashes(destination)
        comet_destination = comet_destination.split("/")
        if len(comet_destination) == 2:
            workspace_dst, project_dst = comet_destination
        elif len(comet_destination) == 1:
            workspace_dst = comet_destination[0]
            project_dst = None
        else:
            raise Exception("invalid COMET_DESTINATION: %r" % destination)

        comet_source = remove_extra_slashes(source)
        comet_source = comet_source.split("/")

        if len(comet_source) == 3:
            workspace_src, project_src, experiment_src = comet_source
        elif len(comet_source) == 2:
            workspace_src, project_src = comet_source
            experiment_src = "*"
        elif len(comet_source) == 1:
            workspace_src = comet_source[0]
            project_src, experiment_src = "*", "*"
        else:
            raise Exception("invalid COMET_SOURCE: %r" % source)

        # First check to make sure workspace_dst exists:
        workspaces = self.api.get_workspaces()
        if workspace_dst not in workspaces:
            raise Exception(
                f"{workspace_dst} does not exist; use the Comet UI to create it"
            )

        # For checking if the project_dst exists below:
        projects = self.api.get_projects(workspace_dst)

        for experiment_folder in self.get_experiment_folders(
            workspace_src, project_src, experiment_src
        ):
            if experiment_folder.count("/") >= 2:
                folder_workspace, folder_project, folder_experiment = (
                    experiment_folder
                ).rsplit("/", 2)
            else:
                print("Unknown folder: %r; ignoring" % experiment_folder)
                continue
            if folder_experiment in ["project_metadata.json"]:
                continue
            temp_project_dst = project_dst
            if temp_project_dst is None:
                temp_project_dst = folder_project

            # Next, check if the project_dst exists:
            if temp_project_dst not in projects:
                project_metadata_path = os.path.join(
                    workspace_src, project_src, "project_metadata.json"
                )
                if os.path.exists(project_metadata_path):
                    with open(project_metadata_path) as fp:
                        project_metadata = json.load(fp)
                    self.api.create_project(
                        workspace_dst,
                        temp_project_dst,
                        project_description=project_metadata["projectDescription"],
                        public=project_metadata["public"],
                    )
                projects.append(temp_project_dst)

            if symlink:
                print(
                    f"Creating symlink from {workspace_src}/{project_src}/{experiment_src} to {workspace_dst}/{temp_project_dst}"
                )
                experiment = APIExperiment(previous_experiment=experiment_src)
                experiment.create_symlink(temp_project_dst)
                print(
                    f"    New symlink created: {self.api._get_url_server()}/{workspace_dst}/{temp_project_dst}/{experiment_src}"
                )
            elif "experiments" not in self.ignore:
                self.copy_experiment_to(
                    experiment_folder, workspace_dst, temp_project_dst
                )

    def create_experiment(self, workspace_dst, project_dst, offline=True):
        """
        Create an experiment in destination workspace
        and project, and return an Experiment.
        """
        if not self.quiet:
            print("Creating experiment...")

        ExperimentClass = OfflineExperiment if offline else Experiment
        experiment = ExperimentClass(
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

        def filter_messages(method):
            def filtered_method(message):
                if hasattr(message, "context") and message.context == "ignore":
                    return
                method(message)

            return filtered_method

        experiment.streamer.put_message_in_q = filter_messages(
            experiment.streamer.put_message_in_q
        )
        return experiment

    def get_experiment_folders(self, workspace_src, project_src, experiment_src):
        for path in glob.iglob(f"{workspace_src}/{project_src}/{experiment_src}"):
            if any(
                [path.endswith("~"), path.endswith(".json"), path.endswith(".jsonl")]
            ):
                continue
            else:
                yield path

    def copy_experiment_to(self, experiment_folder, workspace_dst, project_dst):
        title = experiment_folder
        # See if there is a name:
        filename = os.path.join(experiment_folder, "others.jsonl")
        if os.path.isfile(filename):
            with open(filename) as fp:
                line = fp.readline()
                while line:
                    others_json = json.loads(line)
                    if others_json["name"] == "Name":
                        title = (
                            f"{experiment_folder} (\"{others_json['valueCurrent']}\")"
                        )
                        break
                    line = fp.readline()
        print(f"Copying from {title} to {workspace_dst}/{project_dst}...")

        # Copy other project-level items to an experiment:
        if "reports" not in self.ignore and not self.copied_reports:
            experiment = None
            workspace_src, project_src, _ = experiment_folder.split("/")
            reports = os.path.join(workspace_src, project_src, "reports", "*")
            for filename in glob.glob(reports):
                if filename.endswith("reports_metadata.jsonl"):
                    continue
                basename = os.path.basename(filename)
                artifact = Artifact(basename, "Report")
                artifact.add(filename)
                if experiment is None:
                    experiment = self.create_experiment(
                        workspace_dst, project_dst, offline=False
                    )
                    experiment.log_other("Name", "Reports")
                experiment.log_artifact(artifact)
            if experiment:
                experiment.end()
            self.copied_reports = True

        experiment = self.create_experiment(workspace_dst, project_dst)
        # copy experiment_folder stuff to experiment
        # copy all resources to existing or new experiment
        self.log_all(experiment, experiment_folder)
        experiment.end()

        print(
            f"Uploading {experiment.offline_directory}/{experiment._get_offline_archive_file_name()}"
        )
        url = upload_single_offline_experiment(
            offline_archive_path=os.path.join(
                experiment.offline_directory,
                experiment._get_offline_archive_file_name(),
            ),
            settings=self.api.config,
            force_upload=False,
        )
        if url:
            print("Experiment copied to: %s" % url)
        else:
            print("ERROR: this experiment failed to copy")

    def log_metadata(self, experiment, filename):
        if not self.quiet:
            with experiment.context_manager("ignore"):
                print("log_metadata...")
        if os.path.exists(filename):
            metadata = json.load(open(filename))
            experiment.add_tags(metadata.get("tags", []))
            if metadata.get("fileName", None):
                experiment.set_filename(metadata["fileName"])

    def log_system_details(self, experiment, filename):
        if not self.quiet:
            with experiment.context_manager("ignore"):
                print("log_system_details...")
        if os.path.exists(filename):
            system = json.load(open(filename))

            ## System info:
            message = SystemDetailsMessage(
                command=system.get("command", None),
                env=system.get("env", None),
                hostname=system.get("hostname", None),
                ip=system.get("ip", None),
                machine=system.get("machine", None),
                os_release=system.get("osRelease", None),
                os_type=system.get("osType", None),
                os=system.get("os", None),
                pid=system.get("pid", None),
                processor=system.get("processor", None),
                python_exe=system.get("executable", None),
                python_version_verbose=system.get("pythonVersionVerbose", None),
                python_version=system.get("pythonVersion", None),
                user=system.get("user", None),
            )
            experiment._enqueue_message(message)

    def log_graph(self, experiment, filename):
        if not self.quiet:
            with experiment.context_manager("ignore"):
                print("log_graph...")
        if os.path.exists(filename):
            experiment.set_model_graph(open(filename).read())

    def log_assets(self, experiment, path, assets_metadata):
        if not self.quiet:
            with experiment.context_manager("ignore"):
                print("log_assets...")
        for log_filename in assets_metadata:
            log_as_filename = assets_metadata[log_filename].get(
                "logAsFileName",
                None,
            )
            step = assets_metadata[log_filename].get("step", None)
            epoch = assets_metadata[log_filename].get("epoch", None)
            asset_type = assets_metadata[log_filename].get("type", None)
            asset_type = asset_type if asset_type else "asset"
            if asset_type in self.ignore:
                continue
            if log_filename.startswith("/"):
                filename = os.path.join(path, asset_type, log_filename[1:])
            else:
                filename = os.path.join(path, asset_type, log_filename)

            if not os.path.isfile(filename):
                with experiment.context_manager("ignore"):
                    print("Missing file %r: unable to copy" % filename)
                continue

            metadata = assets_metadata[log_filename].get("metadata")
            metadata = json.loads(metadata) if metadata else {}

            if asset_type == "notebook":
                experiment.log_notebook(filename)  # done!
            elif asset_type == "video":
                name = os.path.basename(filename)
                binary_io = open(filename, "rb")

                experiment.log_video(
                    binary_io, name=log_as_filename or name, step=step, epoch=epoch
                )  # done!
                # FIXME:
                # TODO: what to do about assets referenced in confusion matrix?
                # elif asset_type == "embedding":
                # TODO: what to do about assets referenced in embedding?
            elif asset_type == "model-element":
                name = os.path.basename(filename)
                experiment.log_model(name, filename)
            else:
                binary_io = open(filename, "rb")

                experiment._log_asset(
                    binary_io,
                    file_name=log_as_filename or log_filename,
                    copy_to_tmp=True,
                    asset_type=asset_type,
                    metadata=metadata,
                    step=step,
                )  # done!

    def log_code(self, experiment, filename):
        """ """
        if not self.quiet:
            with experiment.context_manager("ignore"):
                print("log_code...")
        if os.path.exists(filename):
            if os.path.isfile(filename):
                experiment.log_code(str(filename))
            elif os.path.isdir(filename):
                experiment.log_code(folder=str(filename))

    def log_requirements(self, experiment, filename):
        """
        Requirements (pip packages)
        """
        if not self.quiet:
            with experiment.context_manager("ignore"):
                print("log_requirements...")
        if os.path.exists(filename):
            installed_packages_list = [package.strip() for package in open(filename)]
            if installed_packages_list is None:
                return
            message = InstalledPackagesMessage(
                installed_packages=installed_packages_list,
            )
            experiment._enqueue_message(message)

    def log_metrics(self, experiment, filename):
        """ """
        if os.path.exists(filename):
            if not self.quiet:
                with experiment.context_manager("ignore"):
                    print("log_metrics %s..." % filename)

            for line in open(filename):
                dict_line = json.loads(line)
                name = dict_line["metricName"]
                if name.startswith("sys.") and "system-metrics" in self.ignore:
                    continue
                value = dict_line.get("metricValue", None)
                step = dict_line.get("step", None)
                epoch = dict_line.get("epoch", None)
                context = dict_line.get("runContext", None)
                timestamp = dict_line.get("timestamp", None)
                message = MetricMessage(
                    context=context,
                    timestamp=timestamp,
                )
                message.set_metric(name, value, step=step, epoch=epoch)
                experiment._enqueue_message(message)

    def log_metrics_split(self, experiment, folder):
        """ """
        summary_filename = os.path.join(folder, "metrics_summary.jsonl")
        if os.path.exists(summary_filename):
            if not self.quiet:
                with experiment.context_manager("ignore"):
                    print("log_metrics from %s..." % summary_filename)

            for line in open(summary_filename):
                metric_summary = json.loads(line)
                self.log_metrics(
                    experiment,
                    os.path.join(
                        folder, "metrics", "metric_%05d.jsonl" % metric_summary["count"]
                    ),
                )

    def log_parameters(self, experiment, filename):
        """ """
        if not self.quiet:
            with experiment.context_manager("ignore"):
                print("log_parameters...")
        if os.path.exists(filename):
            parameters = json.load(open(filename))
            parameter_dictionary = {
                parameter["name"]: parameter["valueCurrent"] for parameter in parameters
            }
            experiment.log_parameters(parameter_dictionary, nested_support=True)

    def log_others(self, experiment, filename):
        """ """
        if not self.quiet:
            with experiment.context_manager("ignore"):
                print("log_others...")
        if os.path.exists(filename):
            for line in open(filename):
                dict_line = json.loads(line)
                name = dict_line["name"]
                value = dict_line["valueCurrent"]
                experiment.log_other(key=name, value=value)

    def log_output(self, experiment, output_file):
        """ """
        if not self.quiet:
            with experiment.context_manager("ignore"):
                print("log_output...")
        if os.path.exists(output_file):
            for line in open(output_file):
                message = StandardOutputMessage(
                    output=line,
                    stderr=False,
                )
                experiment._enqueue_message(message)

    def log_html(self, experiment, filename):
        if not self.quiet:
            with experiment.context_manager("ignore"):
                print("log_html...")
        if os.path.exists(filename):
            html = open(filename).read()
            message = HtmlMessage(
                html=html,
            )
            experiment._enqueue_message(message)

    def log_git_metadata(self, experiment, filename):
        if os.path.exists(filename):
            with open(filename) as fp:
                metadata = json.load(fp)

            git_metadata = {
                "parent": metadata.get("parent", None),
                "repo_name": None,
                "status": None,
                "user": metadata.get("user", None),
                "root": metadata.get("root", None),
                "branch": metadata.get("branch", None),
                "origin": metadata.get("origin", None),
            }
            message = GitMetadataMessage(
                git_metadata=git_metadata,
            )
            experiment._enqueue_message(message)

    def log_git_patch(self, experiment, filename):
        if os.path.exists(filename):
            with open(filename) as fp:
                git_patch = fp.read()

            _, zip_path = compress_git_patch(git_patch)
            processor = GitPatchUploadProcessor(
                TemporaryFilePath(zip_path),
                experiment.asset_upload_limit,
                url_params=None,
                metadata=None,
                copy_to_tmp=False,
                error_message_identifier=None,
                tmp_dir=experiment.tmpdir,
                critical=False,
            )
            upload_message = processor.process()
            if upload_message:
                experiment._enqueue_message(upload_message)

    def log_all(self, experiment, experiment_folder):
        """ """
        # FIXME: missing notes (edited by human, not logged programmatically)
        if "metrics" not in self.ignore:
            # All together, in one file:
            self.log_metrics(
                experiment, os.path.join(experiment_folder, "metrics.jsonl")
            )
            # In separate files:
            self.log_metrics_split(experiment, experiment_folder)

        if "metadata" not in self.ignore:
            self.log_metadata(
                experiment, os.path.join(experiment_folder, "metadata.json")
            )

        if "parameters" not in self.ignore:
            self.log_parameters(
                experiment, os.path.join(experiment_folder, "parameters.json")
            )

        if "others" not in self.ignore:
            self.log_others(experiment, os.path.join(experiment_folder, "others.jsonl"))

        if "assets" not in self.ignore:
            assets_metadata_filename = os.path.join(
                experiment_folder, "assets", "assets_metadata.jsonl"
            )
            assets_metadata = {}
            if os.path.exists(assets_metadata_filename):
                for line in open(assets_metadata_filename):
                    data = json.loads(line)
                    assets_metadata[data["fileName"]] = data

                self.log_assets(
                    experiment,
                    os.path.join(experiment_folder, "assets"),
                    assets_metadata,
                )

        if "output" not in self.ignore:
            self.log_output(
                experiment, os.path.join(experiment_folder, "run/output.txt")
            )

        if "requirements" not in self.ignore:
            self.log_requirements(
                experiment, os.path.join(experiment_folder, "run/requirements.txt")
            )

        if "model-graph" not in self.ignore:
            self.log_graph(
                experiment, os.path.join(experiment_folder, "run/graph_definition.txt")
            )

        if "html" not in self.ignore:
            # NOTE: also logged as html asset
            html_filenames = os.path.join(experiment_folder, "assets", "html", "*")
            for html_filename in glob.glob(html_filenames):
                self.log_html(experiment, html_filename)
            # Deprecated:
            self.log_html(
                experiment,
                os.path.join(experiment_folder, "experiment.html"),
            )

        if "system-details" not in self.ignore:
            self.log_system_details(
                experiment, os.path.join(experiment_folder, "system_details.json")
            )

        if "git" not in self.ignore:
            self.log_git_metadata(
                experiment, os.path.join(experiment_folder, "run", "git_metdata.json")
            )
            self.log_git_patch(
                experiment, os.path.join(experiment_folder, "run", "git_diff.patch")
            )

        if "code" not in self.ignore:
            code_folder = os.path.join(experiment_folder, "run", "code")
            self.log_code(experiment, code_folder)
            # Deprecated:
            self.log_code(
                experiment, os.path.join(experiment_folder, "run", "script.py")
            )


def main(args):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    get_parser_arguments(parser)
    parsed_args = parser.parse_args(args)
    copy(parsed_args)


if __name__ == "__main__":
    # Called via `python -m cometx.cli.copy ...`
    main(sys.argv[1:])
