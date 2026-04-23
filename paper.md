---
title: 'bibcleaner: A command-line tool for deduplicating and normalising BibTeX bibliography files'
tags:
  - Python
  - bibliography
  - BibTeX
  - LaTeX
  - reproducibility
authors:
  - name: Vaibhav Deshmukh
    orcid: 0000-0001-6745-7062
    affiliation: 1
affiliations:
  - name: Independent Researcher, Nagpur, India
    index: 1
date: 23 April 2026
bibliography: paper.bib
---

# Summary

`bibcleaner` is a command-line tool that parses, deduplicates, and normalises BibTeX `.bib` files commonly used in LaTeX documents. Researchers managing large bibliographies frequently encounter duplicate entries, inconsistent field formatting, missing required fields, and encoding errors accumulated from merging references from multiple sources. `bibcleaner` automates detection and resolution of these issues through a configurable pipeline: it parses BibTeX files using a robust grammar, identifies duplicates by DOI, title similarity, and author-year matching, normalises author name formatting, escapes special characters, and validates required fields per entry type.

# Statement of Need

Manually maintaining large `.bib` files is error-prone and time-consuming. Duplicate citations silently inflate reference counts; missing fields cause compilation errors; inconsistent author formats complicate citation matching across papers. Existing tools such as `bibtool` address some of these issues but require complex configuration and lack modern Python packaging for integration into automated workflows. `bibcleaner` is designed for straightforward installation via pip and use in CI/CD pipelines, Makefiles, and pre-commit hooks, enabling reproducible, clean bibliographies as part of normal document preparation workflows [@stodden2016enhancing; @pineau2021improving].

# Acknowledgements

The author used Claude (Anthropic) for drafting portions of this manuscript. All scientific claims and design decisions are the author's own.

# References
