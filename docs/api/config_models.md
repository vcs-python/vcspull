# Configuration Models - `vcspull.config.models`

This page documents the Pydantic models used to configure VCSPull.

## Repository Model

The Repository model represents a single repository configuration.

```{eval-rst}
.. autopydantic_model:: vcspull.config.models.Repository
   :inherited-members: BaseModel
   :model-show-json: True
   :model-show-field-summary: True
   :field-signature-prefix: param
```

## Settings Model

The Settings model controls global behavior of VCSPull.

```{eval-rst}
.. autopydantic_model:: vcspull.config.models.Settings
   :inherited-members: BaseModel
   :model-show-json: True
   :model-show-field-summary: True
   :field-signature-prefix: param
```

## VCSPullConfig Model

The VCSPullConfig model is the root configuration model for VCSPull.

```{eval-rst}
.. autopydantic_model:: vcspull.config.models.VCSPullConfig
   :inherited-members: BaseModel
   :model-show-json: True
   :model-show-field-summary: True
   :field-signature-prefix: param
``` 