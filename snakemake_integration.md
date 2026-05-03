# Snakemake Integration Research

## Background

This document summarises my research into using Snakemake as the workflow engine for the LLVM benchmarking pipeline. The question came up in the supervisor meeting on 22 April 2026, where we compared Snakemake and Nextflow and agreed that Snakemake was the more suitable direction. The main open question left after that meeting was how well Snakemake can be integrated with the existing Python code, and whether it can be driven programmatically rather than purely from the command line.

## Why Snakemake Over Nextflow

Nextflow was ruled out mainly because it runs on the JVM via Groovy, which would add a non-trivial dependency to an environment that is otherwise just Python and standard Linux build tools. Beyond the environment overhead, Nextflow's core abstraction — channels passing data between processes — is designed for pipelines that fan out to many parallel tasks, such as processing hundreds of genomic samples. Our pipeline does not have that shape. It is a linear sequence of heavy build steps with only a small amount of parallelism available, so Nextflow's model does not offer much benefit and would make the code harder to follow.

Snakemake is a natural fit for several reasons. It is Python-based, so the learning curve is low and the tooling integrates cleanly with the rest of the project. More importantly, its dependency model maps almost directly onto what the pipeline already does. The current `benchmark_pipeline.py` already performs manual dependency checks — for example, it checks whether the Clang binary exists before deciding to skip the LLVM build step. Snakemake formalises this pattern: each rule declares its input and output files, and Snakemake figures out what needs to be re-run. This means we can remove a lot of the hand-written orchestration logic and let the framework handle it.

## How the Pipeline Maps to Snakemake Rules

The existing pipeline has five logical stages: building LLVM, building the Official Test Suite, building the RAJA Performance Suite, running the benchmarks, and generating the report. These stages have clear file-based dependencies between them. The LLVM binary (`clang++`) is produced by the first stage and consumed by the next two. The build outputs of the Official and RAJA suites are consumed by the benchmark runner. The raw result files are consumed by the report generator.

Translating this into a Snakemake `Snakefile` is straightforward. Each stage becomes a rule with explicit `input` and `output` fields. Once that mapping is in place, Snakemake handles skipping steps whose outputs already exist, re-running steps whose inputs have changed, and running independent steps (the two test suite builds) in parallel when `-j 2` is passed. The latter is a concrete improvement over the current code, which builds the two suites sequentially even though neither depends on the other.

A further benefit is multi-version parameterisation. Because the pipeline is currently driven by a single version tag in `config.yml`, comparing performance across LLVM versions requires running the script multiple times manually. With Snakemake's `expand()` helper it becomes straightforward to declare a set of versions and have Snakemake produce results for all of them in one invocation.

## Integrating with Existing Python Code

Snakemake supports three ways to invoke logic from a rule. The first is a `script:` directive, which runs an external Python script and injects a `snakemake` object into it so the rule's input and output paths are accessible. This is the cleanest option for `parse_results.py` and `generate_report.py`, which already operate on files and would need only minor adjustments. The second option is a `run:` block, which embeds Python code directly inside the rule — useful for small pieces of logic that do not warrant a separate file. The third option is a `shell:` directive for invoking command-line tools directly, which would work for the `lit` and `ninja` invocations in the build steps.

Snakemake also has a Python API via `snakemake.snakemake()`, which means the entire workflow can be triggered from within a Python script rather than from the command line. This is relevant for the idea discussed in the meeting of triggering a pipeline run automatically when a new LLVM release is detected. The pattern would be: an external trigger (a cron job or CI job) detects a new release tag, updates `config.yml`, and then calls `snakemake.snakemake()` programmatically to start the run.

## Notes on the LLVM Repository Monitoring Idea

It is worth clarifying one point from the meeting discussion. Snakemake itself does not poll remote repositories — it only responds to changes in the local filesystem. So monitoring for new LLVM releases still requires an external mechanism. A practical setup would be a scheduled job that checks the LLVM GitHub repository for new tags, updates the version field in `config.yml` when a new one is found, and then invokes Snakemake. Snakemake would then determine which output files are missing for the new version and run only the necessary steps. This is a reasonable division of responsibilities: Snakemake handles what to run and in what order, while the external trigger handles when to start.

## Proposed Migration Approach

The migration can be done in three steps. The first is to write a `Snakefile` that calls the existing `benchmark_pipeline.py` as a single shell command, just to validate that Snakemake can manage the top-level dependency and logging. The second is to pull `parse_results.py` and `generate_report.py` out into separate Snakemake rules using the `script:` directive, since these are already cleanly separated scripts with well-defined inputs and outputs. The third is to break the internal stages of `benchmark_pipeline.py` into individual rules, which allows the two test suite builds to run in parallel and removes the hand-written orchestration logic from the script entirely. Each step builds on the previous one and leaves the pipeline in a working state, so the migration can proceed at whatever pace is convenient.
