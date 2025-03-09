# Configuration Schema

This page provides the detailed JSON Schema for the VCSPull configuration.

## JSON Schema

The following schema is automatically generated from the VCSPull configuration models.

```{eval-rst}
.. autopydantic_model:: vcspull.config.models.VCSPullConfig
   :model-show-json-schema: True
   :model-show-field-summary: True
   :field-signature-prefix: param
```

## Repository Schema

Individual repository configuration schema:

```{eval-rst}
.. autopydantic_model:: vcspull.config.models.Repository
   :model-show-json-schema: True
   :model-show-field-summary: True
   :field-signature-prefix: param
```

## Settings Schema

Global settings configuration schema:

```{eval-rst}
.. autopydantic_model:: vcspull.config.models.Settings
   :model-show-json-schema: True
   :model-show-field-summary: True
   :field-signature-prefix: param
``` 