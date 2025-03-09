# Pydantic v2 

> Fast and extensible data validation library for Python using type annotations.

## Introduction

Pydantic is the most widely used data validation library for Python. It uses type annotations to define data schemas and provides powerful validation, serialization, and documentation capabilities.

### Key Features

- **Type-driven validation**: Uses Python type hints for schema definition and validation
- **Performance**: Core validation logic written in Rust for maximum speed
- **Flexibility**: Supports strict and lax validation modes
- **Extensibility**: Customizable validators and serializers
- **Ecosystem integration**: Works with FastAPI, Django Ninja, SQLModel, LangChain, and many others
- **Standard library compatibility**: Works with dataclasses, TypedDict, and more

## Installation

```bash
# Basic installation
uv add pydantic

# With optional dependencies
uv add 'pydantic[email,timezone]'

# From repository
uv add 'git+https://github.com/pydantic/pydantic@main'
```

### Dependencies

- `pydantic-core`: Core validation logic (Rust)
- `typing-extensions`: Backport of typing module
- `annotated-types`: Constraint types for `typing.Annotated`

#### Optional dependencies

- `email`: Email validation via `email-validator` package
- `timezone`: IANA time zone database via `tzdata` package

## Basic Models

The primary way to define schemas in Pydantic is via models. Models are classes that inherit from `BaseModel` with fields defined as annotated attributes.

```python
import typing as t
from pydantic import BaseModel, ConfigDict


class User(BaseModel):
    id: int
    name: str = 'John Doe'  # Optional with default
    email: t.Optional[str] = None  # Optional field that can be None
    tags: list[str] = []  # List of strings with default empty list
    
    # Model configuration
    model_config = ConfigDict(
        str_max_length=50,  # Maximum string length
        extra='ignore',     # Ignore extra fields in input data
    )
```

### Initialization and Validation

When you initialize a model, Pydantic validates the input data against the field types:

```python
# Valid data
user = User(id=123, email='user@example.com', tags=['staff', 'admin'])

# Type conversion happens automatically
user = User(id='456', tags=['member'])  # '456' is converted to int

# Access fields as attributes
print(user.id)       # 456
print(user.name)     # 'John Doe'
print(user.tags)     # ['member']

# Field validation error
try:
    User(name=123)  # Missing required 'id' field
except Exception as e:
    print(f"Validation error: {e}")
```

### Model Methods

Models provide several useful methods:

```python
# Convert to dictionary
user_dict = user.model_dump()

# Convert to JSON string
user_json = user.model_dump_json()

# Create a copy
user_copy = user.model_copy()

# Get fields set during initialization
print(user.model_fields_set)  # {'id', 'tags'}

# Get model schema
schema = User.model_json_schema()
```

### Nested Models

Models can be nested to create complex data structures:

```python
class Address(BaseModel):
    street: str
    city: str
    country: str
    postal_code: t.Optional[str] = None


class User(BaseModel):
    id: int
    name: str
    address: t.Optional[Address] = None


# Initialize with nested data
user = User(
    id=1,
    name='Alice',
    address={
        'street': '123 Main St',
        'city': 'New York',
        'country': 'USA'
    }
)

# Access nested data
print(user.address.city)  # 'New York'
```

## Field Customization

Fields can be customized using the `Field()` function, which allows specifying constraints, metadata, and other attributes.

### Default Values and Factories

```python
import typing as t
from uuid import uuid4
from datetime import datetime
from pydantic import BaseModel, Field


class Item(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    name: str  # Required field
    description: t.Optional[str] = None  # Optional with None default
    created_at: datetime = Field(default_factory=datetime.now)
    tags: list[str] = Field(default_factory=list)  # Empty list default
    
    # Default factory can use other validated fields
    slug: str = Field(default_factory=lambda data: data['name'].lower().replace(' ', '-'))
```

### Field Constraints

Use constraints to add validation rules to fields:

```python
import typing as t
from pydantic import BaseModel, Field, EmailStr


class User(BaseModel):
    # String constraints
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8, pattern=r'^(?=.*[A-Za-z])(?=.*\d)')
    
    # Numeric constraints
    age: int = Field(gt=0, lt=120)  # Greater than 0, less than 120
    score: float = Field(ge=0, le=100)  # Greater than or equal to 0, less than or equal to 100
    
    # Email validation (requires 'email-validator' package)
    email: EmailStr

    # List constraints
    tags: list[str] = Field(max_length=5)  # Maximum 5 items in list
```

### Field Aliases

Aliases allow field names in the data to differ from Python attribute names:

```python
import typing as t
from pydantic import BaseModel, Field


class User(BaseModel):
    # Different field name for input/output
    user_id: int = Field(alias='id')
    
    # Different field names for input and output
    first_name: str = Field(validation_alias='firstName', serialization_alias='first_name')
    
    # Alias path for nested data
    country_code: str = Field(validation_alias='address.country.code')


# Using alias in instantiation
user = User(id=123, firstName='John', **{'address.country.code': 'US'})

# Access with Python attribute name
print(user.user_id)  # 123
print(user.first_name)  # John

# Serialization uses serialization aliases
print(user.model_dump())  # {'user_id': 123, 'first_name': 'John', 'country_code': 'US'}
print(user.model_dump(by_alias=True))  # {'id': 123, 'first_name': 'John', 'country_code': 'US'}
```

### Frozen Fields

Fields can be made immutable with the `frozen` parameter:

```python
from pydantic import BaseModel, Field


class User(BaseModel):
    id: int = Field(frozen=True)
    name: str


user = User(id=1, name='Alice')
user.name = 'Bob'  # Works fine

try:
    user.id = 2  # This will raise an error
except Exception as e:
    print(f"Error: {e}")
```

### The Annotated Pattern

Use `typing.Annotated` to attach metadata to fields while maintaining clear type annotations:

```python
import typing as t
from pydantic import BaseModel, Field


class Product(BaseModel):
    # Traditional approach
    name: str = Field(min_length=1, max_length=100)
    
    # Annotated approach - preferred for clarity
    price: t.Annotated[float, Field(gt=0)]
    
    # Multiple constraints
    sku: t.Annotated[str, Field(min_length=8, max_length=12, pattern=r'^[A-Z]{3}\d{5,9}$')]
    
    # Constraints on list items
    tags: list[t.Annotated[str, Field(min_length=2, max_length=10)]]
```

## Validators

Pydantic provides custom validators to enforce complex constraints beyond the basic type validation.

### Field Validators

Field validators are functions applied to specific fields that validate or transform values:

```python
import typing as t
from pydantic import BaseModel, ValidationError, field_validator, AfterValidator


class User(BaseModel):
    username: str
    password: str
    
    # Method-based validator with decorator
    @field_validator('username')
    @classmethod
    def validate_username(cls, value: str) -> str:
        if len(value) < 3:
            raise ValueError('Username must be at least 3 characters')
        if not value.isalnum():
            raise ValueError('Username must be alphanumeric')
        return value
    
    # Multiple field validator
    @field_validator('password')
    @classmethod
    def validate_password(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError('Password must be at least 8 characters')
        if not any(c.isupper() for c in value):
            raise ValueError('Password must contain an uppercase letter')
        if not any(c.isdigit() for c in value):
            raise ValueError('Password must contain a digit')
        return value


# You can also use the Annotated pattern
def is_valid_email(value: str) -> str:
    if '@' not in value:
        raise ValueError('Invalid email format')
    return value


class Contact(BaseModel):
    # Using Annotated pattern for validation
    email: t.Annotated[str, AfterValidator(is_valid_email)]
```

### Model Validators

Model validators run after all field validation and can access or modify the entire model:

```python
import typing as t
from pydantic import BaseModel, model_validator


class UserRegistration(BaseModel):
    username: str
    password: str
    password_confirm: str
    
    # Validate before model creation (raw input data) 
    @model_validator(mode='before')
    @classmethod
    def check_passwords_match(cls, data: dict) -> dict:
        # For 'before' validators, data is a dict
        if isinstance(data, dict):
            if data.get('password') != data.get('password_confirm'):
                raise ValueError('Passwords do not match')
        return data
    
    # Validate after model creation (processed model) 
    @model_validator(mode='after')
    def remove_password_confirm(self) -> 'UserRegistration':
        # For 'after' validators, self is the model instance
        self.__pydantic_private__.get('password_confirm')
        # We can modify the model here if needed
        return self


# Usage
try:
    user = UserRegistration(
        username='johndoe',
        password='Password123',
        password_confirm='Password123'
    )
    print(user.model_dump())
except ValidationError as e:
    print(f"Validation error: {e}")
```

### Root Validators

When you need to validate fields in relation to each other:

```python
import typing as t
from datetime import datetime
from pydantic import BaseModel, model_validator


class TimeRange(BaseModel):
    start: datetime
    end: datetime
    
    @model_validator(mode='after')
    def check_dates_order(self) -> 'TimeRange':
        if self.start > self.end:
            raise ValueError('End time must be after start time')
        return self
```

## Serialization

Pydantic models can be converted to dictionaries, JSON, and other formats easily.

### Converting to Dictionaries

```python
import typing as t
from datetime import datetime
from pydantic import BaseModel


class User(BaseModel):
    id: int
    name: str
    created_at: datetime
    is_active: bool = True
    metadata: dict[str, t.Any] = {}


user = User(
    id=1, 
    name='John',
    created_at=datetime.now(),
    metadata={'role': 'admin', 'permissions': ['read', 'write']}
)

# Convert to dictionary
user_dict = user.model_dump()

# Include/exclude specific fields
partial_dict = user.model_dump(include={'id', 'name'})
filtered_dict = user.model_dump(exclude={'metadata'})

# Exclude default values
without_defaults = user.model_dump(exclude_defaults=True)

# Exclude None values
without_none = user.model_dump(exclude_none=True)

# Exclude fields that weren't explicitly set
only_set = user.model_dump(exclude_unset=True)

# Convert using aliases
aliased = user.model_dump(by_alias=True)
```

### Converting to JSON

```python
import typing as t
from datetime import datetime
from pydantic import BaseModel


class User(BaseModel):
    id: int
    name: str
    created_at: datetime


user = User(id=1, name='John', created_at=datetime.now())

# Convert to JSON string
json_str = user.model_dump_json()

# Pretty-printed JSON
pretty_json = user.model_dump_json(indent=2)

# Using custom encoders
json_with_options = user.model_dump_json(
    exclude={'id'},
    indent=4
)
```

### Customizing Serialization

You can customize the serialization process using model configuration or computed fields:

```python
import typing as t
from datetime import datetime
from pydantic import BaseModel, computed_field


class User(BaseModel):
    id: int
    first_name: str
    last_name: str
    date_joined: datetime
    
    @computed_field
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
    
    @computed_field
    def days_since_joined(self) -> int:
        return (datetime.now() - self.date_joined).days


user = User(id=1, first_name='John', last_name='Doe', date_joined=datetime(2023, 1, 1))
print(user.model_dump())
# Output includes computed fields: full_name and days_since_joined
```

## Type Adapters

Type Adapters let you validate and serialize against any Python type without creating a BaseModel:

```python
import typing as t
from pydantic import TypeAdapter, ValidationError
from typing_extensions import TypedDict


# Works with standard Python types
int_adapter = TypeAdapter(int)
value = int_adapter.validate_python("42")  # 42
float_list_adapter = TypeAdapter(list[float])
values = float_list_adapter.validate_python(["1.1", "2.2", "3.3"])  # [1.1, 2.2, 3.3]

# Works with TypedDict
class User(TypedDict):
    id: int
    name: str


user_adapter = TypeAdapter(User)
user = user_adapter.validate_python({"id": "1", "name": "John"})  # {'id': 1, 'name': 'John'}

# Works with nested types
nested_adapter = TypeAdapter(list[dict[str, User]])
data = nested_adapter.validate_python([
    {
        "user1": {"id": "1", "name": "John"},
        "user2": {"id": "2", "name": "Jane"}
    }
])

# Serialization
json_data = user_adapter.dump_json(user)  # b'{"id":1,"name":"John"}'

# JSON schema
schema = user_adapter.json_schema()
```

### Performance Tips

Create Type Adapters once and reuse them for best performance:

```python
import typing as t
from pydantic import TypeAdapter

# Create once, outside any loops
LIST_INT_ADAPTER = TypeAdapter(list[int])

# Reuse in performance-critical sections
def process_data(raw_data_list):
    results = []
    for raw_item in raw_data_list:
        # Reuse the adapter for each item
        validated_items = LIST_INT_ADAPTER.validate_python(raw_item)
        results.append(sum(validated_items))
    return results
```

### Working with Forward References

Type Adapters support deferred schema building for forward references:

```python
import typing as t
from pydantic import TypeAdapter, ConfigDict

# Deferred build with forward reference
tree_adapter = TypeAdapter("Tree", ConfigDict(defer_build=True))

# Define the type later
class Tree:
    value: int
    children: list["Tree"] = []

# Manually rebuild schema when types are available
tree_adapter.rebuild()

# Now use the adapter
tree = tree_adapter.validate_python({"value": 1, "children": [{"value": 2, "children": []}]})
```

## JSON Schema

Generate JSON Schema from Pydantic models for validation, documentation, and API specifications.

### Basic Schema Generation

```python
import typing as t
import json
from enum import Enum
from pydantic import BaseModel, Field


class UserType(str, Enum):
    standard = "standard"
    admin = "admin"
    guest = "guest"


class User(BaseModel):
    """User account information"""
    id: int
    name: str
    email: t.Optional[str] = None
    user_type: UserType = UserType.standard
    is_active: bool = True


# Generate JSON Schema
schema = User.model_json_schema()
print(json.dumps(schema, indent=2))
```

### Schema Customization

You can customize the generated schema using Field parameters or ConfigDict:

```python
import typing as t
from pydantic import BaseModel, Field, ConfigDict


class Product(BaseModel):
    """Product information schema"""
    
    model_config = ConfigDict(
        title="Product Schema",
        json_schema_extra={
            "examples": [
                {
                    "id": 1,
                    "name": "Smartphone",
                    "price": 699.99,
                    "tags": ["electronics", "mobile"]
                }
            ]
        }
    )
    
    id: int
    name: str = Field(
        title="Product Name",
        description="The name of the product",
        min_length=1,
        max_length=100
    )
    price: float = Field(
        title="Product Price",
        description="The price in USD",
        gt=0
    )
    tags: list[str] = Field(
        default_factory=list,
        title="Product Tags",
        description="List of tags for categorization"
    )


# Generate schema with all references inline
schema = Product.model_json_schema(ref_template="{model}")
```

### OpenAPI Integration

Pydantic schemas can be used directly with FastAPI for automatic API documentation:

```python
import typing as t
from fastapi import FastAPI
from pydantic import BaseModel, Field


class Item(BaseModel):
    name: str = Field(description="The name of the item")
    price: float = Field(gt=0, description="The price of the item in USD")
    is_offer: bool = False


app = FastAPI()


@app.post("/items/", response_model=Item)
async def create_item(item: Item):
    """
    Create a new item.
    
    The API will automatically validate the request based on the Pydantic model
    and generate OpenAPI documentation.
    """
    return item
```

## Model Configuration

Pydantic models can be configured using the `model_config` attribute or class arguments.

### Configuration with ConfigDict

```python
import typing as t
from pydantic import BaseModel, ConfigDict


class User(BaseModel):
    model_config = ConfigDict(
        # Strict type checking
        strict=False,  # Default is False, set True to disallow any coercion
        
        # Schema configuration
        title='User Schema',
        json_schema_extra={'examples': [{'id': 1, 'name': 'John'}]},
        
        # Additional fields behavior
        extra='ignore',  # 'ignore', 'allow', or 'forbid'
        
        # Validation behavior
        validate_default=True,
        validate_assignment=False,
        
        # String constraints
        str_strip_whitespace=True,
        str_to_lower=False,
        str_to_upper=False,
        
        # Serialization
        populate_by_name=True,  # Allow populating models with alias names
        use_enum_values=False,  # Use enum values instead of enum instances when serializing
        arbitrary_types_allowed=False,
        
        # Frozen settings
        frozen=False,  # Make the model immutable
    )
    
    id: int
    name: str


# Alternative: Using class arguments
class ReadOnlyUser(BaseModel, frozen=True):
    id: int
    name: str
```

### Global Configuration

Create a base class with your preferred configuration:

```python
import typing as t
from pydantic import BaseModel, ConfigDict


class PydanticBase(BaseModel):
    """Base model with common configuration."""
    model_config = ConfigDict(
        validate_assignment=True,
        extra='forbid',
        str_strip_whitespace=True
    )


class User(PydanticBase):
    """Inherits configuration from PydanticBase."""
    name: str
    email: str
```

## Dataclasses

Pydantic provides dataclass support for standard Python dataclasses with validation:

```python
import typing as t
import dataclasses
from datetime import datetime
from pydantic import Field, TypeAdapter, ConfigDict
from pydantic.dataclasses import dataclass


# Basic usage
@dataclass
class User:
    id: int
    name: str = 'John Doe'
    created_at: datetime = None


# With pydantic field
@dataclass
class Product:
    id: int
    name: str
    price: float = Field(gt=0)
    tags: list[str] = dataclasses.field(default_factory=list)


# With configuration
@dataclass(config=ConfigDict(validate_assignment=True, extra='forbid'))
class Settings:
    api_key: str
    debug: bool = False


# Using validation
user = User(id='123')  # String converted to int
print(user)  # User(id=123, name='John Doe', created_at=None)

# Access to validation and schema methods through TypeAdapter
user_adapter = TypeAdapter(User)
schema = user_adapter.json_schema()
json_data = user_adapter.dump_json(user)
```

## Strict Mode

Pydantic provides strict mode to disable type coercion (e.g., converting strings to numbers):

### Field-Level Strict Mode

```python
import typing as t
from pydantic import BaseModel, Field, Strict, StrictInt, StrictStr


class User(BaseModel):
    # Field-level strict mode using Field
    id: int = Field(strict=True)  # Only accepts actual integers
    
    # Field-level strict mode using Annotated
    name: t.Annotated[str, Strict()]  # Only accepts actual strings
    
    # Using built-in strict types
    age: StrictInt  # Shorthand for Annotated[int, Strict()]
    email: StrictStr  # Shorthand for Annotated[str, Strict()]
```

### Model-Level Strict Mode

```python
import typing as t
from pydantic import BaseModel, ConfigDict, ValidationError


class User(BaseModel):
    model_config = ConfigDict(strict=True)  # Applies to all fields
    
    id: int
    name: str


# This will fail
try:
    user = User(id='123', name='John')
except ValidationError as e:
    print(e)
    """
    2 validation errors for User
    id
      Input should be a valid integer [type=int_type, input_value='123', input_type=str]
    name
      Input should be a valid string [type=str_type, input_value='John', input_type=str]
    """
```

### Method-Level Strict Mode

```python
import typing as t
from pydantic import BaseModel, ValidationError


class User(BaseModel):
    id: int
    name: str


# Standard validation allows coercion
user1 = User.model_validate({'id': '123', 'name': 'John'})  # Works fine

# Validation with strict mode at call time
try:
    user2 = User.model_validate({'id': '123', 'name': 'John'}, strict=True)
except ValidationError:
    print("Strict validation failed")
```

## Additional Features

### Computed Fields

Add computed properties that appear in serialized output:

```python
import typing as t
from datetime import datetime
from pydantic import BaseModel, computed_field


class User(BaseModel):
    first_name: str
    last_name: str
    birth_date: datetime
    
    @computed_field
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
    
    @computed_field
    def age(self) -> int:
        delta = datetime.now() - self.birth_date
        return delta.days // 365
```

### RootModel for Simple Types with Validation

Use RootModel to add validation to simple types:

```python
import typing as t
from pydantic import RootModel, Field


# Validate a list of integers
class IntList(RootModel[list[int]]):
    root: list[int] = Field(min_length=1)  # Must have at least one item


# Usage
valid_list = IntList([1, 2, 3])
print(valid_list.root)  # [1, 2, 3]
```

### Discriminated Unions

Use discriminated unions for polymorphic models:

```python
import typing as t
from enum import Enum
from pydantic import BaseModel, Field


class PetType(str, Enum):
    cat = 'cat'
    dog = 'dog'


class Pet(BaseModel):
    pet_type: PetType
    name: str


class Cat(Pet):
    pet_type: t.Literal[PetType.cat]
    lives_left: int = 9


class Dog(Pet):
    pet_type: t.Literal[PetType.dog]
    likes_walks: bool = True


# Using Annotated with Field to specify the discriminator
PetUnion = t.Annotated[t.Union[Cat, Dog], Field(discriminator='pet_type')]

pets: list[PetUnion] = [
    Cat(name='Felix'),
    Dog(name='Fido', likes_walks=False)
]
```

## Migration from Pydantic v1

If you're migrating from Pydantic v1 to v2, there are several important changes to be aware of:

### Key Changes in v2

```python
# v1
from pydantic import BaseModel

# v2 - same import, but different functionality
from pydantic import BaseModel

# If you need v1 compatibility
from pydantic.v1 import BaseModel  # Access v1 functionality
```

### Migration Tool

Pydantic provides an automated migration tool:

```bash
# Install migration tool
pip install bump-pydantic

# Use the tool
cd /path/to/your/project
bump-pydantic your_package_directory
```

### Main API Changes

- `parse_obj` → `model_validate`
- `parse_raw` → `model_validate_json`
- `schema` → `model_json_schema`
- `dict` → `model_dump`
- `json` → `model_dump_json`
- `copy` → `model_copy`
- `update_forward_refs` → `model_rebuild`
- `construct` → `model_construct`

### Error Handling

Pydantic provides detailed error information through the `ValidationError` class:

```python
import typing as t
from pydantic import BaseModel, ValidationError


class User(BaseModel):
    id: int
    name: str
    email: str


try:
    User(id="not-an-int", name=None, email="invalid-email")
except ValidationError as e:
    # Get all errors
    print(e)
    
    # Get error details
    print(f"Error count: {e.error_count()}")
    
    # Get detailed error list
    for error in e.errors():
        print(f"Location: {error['loc']}")
        print(f"Type: {error['type']}")
        print(f"Message: {error['msg']}")
    
    # Get JSON representation
    error_json = e.json()
```

### Performance Improvements

Pydantic v2 core validation logic is written in Rust, resulting in significant performance improvements:

- Validation is 5-50x faster
- Serialization is 4-20x faster
- Model creation is 2-50x faster

For optimal performance:
- Reuse TypeAdapters instead of creating them repeatedly
- Avoid using abstract types like `Sequence` in favor of concrete types like `list`
- Use `model_construct` when creating models from validated data

## Integrations

Pydantic integrates well with many libraries and development tools.

### Web Frameworks

```python
# FastAPI integration (built on Pydantic)
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class Item(BaseModel):
    name: str
    price: float

@app.post("/items/")
async def create_item(item: Item):
    return item
```

### Development Tools

#### IDE Support

Pydantic works with:

- **PyCharm**: Smart completion, type checking and error highlighting
- **VS Code**: With Python extension, provides validation and autocompletion
- **mypy**: Full type checking support

#### Linting and Testing

```python
# Hypothesis integration for property-based testing
from hypothesis import given
from hypothesis.strategies import builds
from pydantic import BaseModel

class User(BaseModel):
    name: str
    age: int

@given(builds(User))
def test_user(user):
    assert user.age >= 0
```

### Utility Libraries

#### Data Generation

```python
# Generate Pydantic models from JSON data
# pip install datamodel-code-generator
from datamodel_code_generator import generate

code = generate(
    json_data,
    input_file_type='json',
    output_model_name='MyModel'
)
print(code)
```

#### Debugging and Visualization

```python
# Rich integration for pretty printing
# pip install rich
from rich.pretty import pprint
from pydantic import BaseModel

class User(BaseModel):
    name: str
    age: int

user = User(name="John", age=30)
pprint(user)  # Pretty printed output

# Logfire monitoring (created by Pydantic team)
# pip install logfire
import logfire
from pydantic import BaseModel

logfire.configure()
logfire.instrument_pydantic()  # Monitor Pydantic validations

class User(BaseModel):
    name: str
    age: int

user = User(name="John", age=30)  # Validation will be recorded
```

## Best Practices

### Type Annotation Patterns

```python
import typing as t
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


# Prefer concrete types over abstract ones
class Good:
    items: list[int]  # Better performance than Sequence[int]
    data: dict[str, float]  # Better than Mapping[str, float]


# Use Optional for nullable fields
class User:
    name: str  # Required
    middle_name: t.Optional[str] = None  # Optional


# Use Union for multiple types (Python 3.10+ syntax)
class Item:
    id: int | str  # Can be either int or string
    tags: list[str] | None = None  # Optional list


# Use Field with default_factory for mutable defaults
class Post:
    title: str
    created_at: datetime = Field(default_factory=datetime.now)
    tags: list[str] = Field(default_factory=list)  # Empty list default
```

### Model Organization

```python
import typing as t
from pydantic import BaseModel


# Use inheritance for shared attributes
class BaseResponse(BaseModel):
    success: bool
    timestamp: int


class SuccessResponse(BaseResponse):
    success: t.Literal[True] = True
    data: dict[str, t.Any]


class ErrorResponse(BaseResponse):
    success: t.Literal[False] = False
    error: str
    error_code: int


# Group related models in modules
# users/models.py
class UserBase(BaseModel):
    email: str
    username: str


class UserCreate(UserBase):
    password: str


class UserResponse(UserBase):
    id: int
    is_active: bool


# Keep models focused on specific use cases
class UserProfile(BaseModel):
    """User profile data shown to other users."""
    username: str
    bio: t.Optional[str] = None
    joined_date: str
```

### Validation Strategies

```python
import typing as t
import re
from pydantic import BaseModel, field_validator, model_validator


# Use field validators for simple field validations
class User(BaseModel):
    username: str
    
    @field_validator('username')
    @classmethod
    def validate_username(cls, v: str) -> str:
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError('Username must be alphanumeric')
        return v


# Use model validators for cross-field validations
class TimeRange(BaseModel):
    start: int
    end: int
    
    @model_validator(mode='after')
    def check_times(self) -> 'TimeRange':
        if self.start >= self.end:
            raise ValueError('End time must be after start time')
        return self


# Use annotated pattern for reusable validations
from pydantic import AfterValidator

def validate_even(v: int) -> int:
    if v % 2 != 0:
        raise ValueError('Value must be even')
    return v

EvenInt = t.Annotated[int, AfterValidator(validate_even)]

class Config(BaseModel):
    port: EvenInt  # Must be an even number
```

### Performance Optimization

```python
import typing as t
from pydantic import BaseModel, TypeAdapter


# Create adapters once, reuse them
INT_LIST_ADAPTER = TypeAdapter(list[int])

def process_numbers(raw_lists: list[list[str]]) -> list[int]:
    results = []
    
    for raw_list in raw_lists:
        # Reuse adapter instead of creating new ones
        numbers = INT_LIST_ADAPTER.validate_python(raw_list)
        results.append(sum(numbers))
    
    return results


# Use model_construct for pre-validated data
class Item(BaseModel):
    id: int
    name: str

# Slow: re-validates data
item1 = Item(id=1, name='example')

# Fast: skips validation for known valid data
item2 = Item.model_construct(id=1, name='example')
```

## Common Pitfalls and Solutions

### Mutable Default Values

```python
import typing as t
from pydantic import BaseModel, Field


# WRONG: Mutable defaults are shared between instances
class Wrong(BaseModel):
    tags: list[str] = []  # All instances will share the same list


# CORRECT: Use Field with default_factory
class Correct(BaseModel):
    tags: list[str] = Field(default_factory=list)  # Each instance gets its own list
```

### Forward References

```python
import typing as t
from pydantic import BaseModel


# WRONG: Direct self-reference without quotes
class WrongNode(BaseModel):
    value: int
    children: list[WrongNode] = []  # Error: WrongNode not defined yet


# CORRECT: String literal reference
class CorrectNode(BaseModel):
    value: int
    children: list["CorrectNode"] = []  # Works with string reference

# Remember to rebuild the model for forward references
CorrectNode.model_rebuild()
```

### Overriding Model Fields

```python
import typing as t
from pydantic import BaseModel


class Parent(BaseModel):
    name: str
    age: int = 30


# WRONG: Field overridden but wrong type
class WrongChild(Parent):
    age: str  # Type mismatch with parent


# CORRECT: Field overridden with compatible type
class CorrectChild(Parent):
    age: int = 18  # Same type, different default
```

### Optional Fields vs. Default Values

```python
import typing as t
from pydantic import BaseModel


# Not what you might expect
class User1(BaseModel):
    # This is Optional but still required - must be provided, can be None
    nickname: t.Optional[str]  


# Probably what you want
class User2(BaseModel):
    # This is Optional AND has a default - doesn't need to be provided
    nickname: t.Optional[str] = None
```

## Conclusion

Pydantic v2 offers robust data validation with a clean, type-driven API and exceptional performance. This document covered:

- Core model usage and customization
- Field validation and constraints
- Schema generation and serialization
- Performance optimization
- Integration with other frameworks
- Migration from v1

For further details, refer to the [official Pydantic documentation](https://docs.pydantic.dev/).

When working with Pydantic:
- Leverage Python's type system
- Use the Annotated pattern for complex field requirements
- Favor concrete container types for better performance
- Reuse TypeAdapters for validation-heavy applications
- Organize models to reflect domain entities

Pydantic's combination of static typing and runtime validation makes it an excellent choice for data-intensive applications, APIs, and projects where data integrity is critical.

## Advanced Features

### Generic Models

Generic models allow you to create reusable model structures with type parameters:

```python
import typing as t
from pydantic import BaseModel


# Define a generic model with TypeVar
T = t.TypeVar('T')


class Response(BaseModel, t.Generic[T]):
    """Generic response wrapper"""
    data: T
    status: str = "success"
    metadata: dict[str, t.Any] = {}


# Use the generic model with specific types
class User(BaseModel):
    id: int
    name: str


# Instantiate with specific type
user_response = Response[User](data=User(id=1, name="John"))
print(user_response.data.name)  # "John"

# Also works with primitive types
int_response = Response[int](data=42)
print(int_response.data)  # 42

# Can be nested
list_response = Response[list[User]](
    data=[
        User(id=1, name="John"),
        User(id=2, name="Jane")
    ]
)
```

### Generic Type Constraints

You can constrain generic type parameters:

```python
import typing as t
from decimal import Decimal
from pydantic import BaseModel


# TypeVar with constraints (must be int, float, or Decimal)
Number = t.TypeVar('Number', int, float, Decimal)


class Statistics(BaseModel, t.Generic[Number]):
    """Statistical calculations on numeric data"""
    values: list[Number]
    
    @property
    def average(self) -> float:
        if not self.values:
            return 0.0
        return sum(self.values) / len(self.values)


# Use with different numeric types
int_stats = Statistics[int](values=[1, 2, 3, 4, 5])
print(int_stats.average)  # 3.0

float_stats = Statistics[float](values=[1.1, 2.2, 3.3])
print(float_stats.average)  # 2.2
```

### Recursive Models

Models can reference themselves to create recursive structures like trees:

```python
import typing as t
from pydantic import BaseModel, Field


class TreeNode(BaseModel):
    """Tree structure with recursive node references"""
    value: str
    children: list["TreeNode"] = Field(default_factory=list)
    parent: t.Optional["TreeNode"] = None


# Must call model_rebuild() to process forward references
TreeNode.model_rebuild()

# Create a tree
root = TreeNode(value="root")
child1 = TreeNode(value="child1", parent=root)
child2 = TreeNode(value="child2", parent=root)
grandchild = TreeNode(value="grandchild", parent=child1)

# Set up the children relationships
root.children = [child1, child2]
child1.children = [grandchild]

# Model is fully connected in both directions
assert root.children[0].value == "child1"
assert grandchild.parent.value == "child1"
assert grandchild.parent.parent.value == "root"
```

### Deeply Nested Models

For deeply nested models, you may need to handle the recursive structure differently:

```python
import typing as t
from pydantic import BaseModel, Field


class Employee(BaseModel):
    """Employee with recursive manager relationship"""
    name: str
    position: str
    # Using Optional to handle leaf nodes (employees with no direct reports)
    direct_reports: t.Optional[list["Employee"]] = None
    manager: t.Optional["Employee"] = None


# Call model_rebuild to process the self-references
Employee.model_rebuild()

# Create an organization structure
ceo = Employee(name="Alice", position="CEO")
cto = Employee(name="Bob", position="CTO", manager=ceo)
dev_manager = Employee(name="Charlie", position="Dev Manager", manager=cto)
dev1 = Employee(name="Dave", position="Developer", manager=dev_manager)
dev2 = Employee(name="Eve", position="Developer", manager=dev_manager)

# Set up the direct reports relationships
ceo.direct_reports = [cto]
cto.direct_reports = [dev_manager]
dev_manager.direct_reports = [dev1, dev2]

# Helper function to print org chart
def print_org_chart(employee: Employee, level: int = 0):
    print("  " * level + f"{employee.name} ({employee.position})")
    if employee.direct_reports:
        for report in employee.direct_reports:
            print_org_chart(report, level + 1)


# Print the organization chart
print_org_chart(ceo)
```

### Settings Management

Pydantic offers `BaseSettings` for configuration management with environment variables:

```python
import typing as t
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Application settings with environment variable support"""
    
    # Configure settings behavior
    model_config = SettingsConfigDict(
        env_file='.env',              # Load from .env file
        env_file_encoding='utf-8',    # Encoding for .env file
        env_nested_delimiter='__',    # For nested settings (e.g., DATABASE__HOST)
        case_sensitive=False,         # Case-insensitive env vars
    )
    
    # App settings with environment variable fallbacks
    app_name: str = "MyApp"
    debug: bool = Field(default=False, description="Enable debug mode")
    api_key: t.Optional[str] = Field(default=None, env="API_SECRET_KEY")
    
    # Database configuration with nested structure
    database_url: str = Field(
        default="sqlite:///./app.db",
        env="DATABASE_URL",
        description="Database connection string"
    )
    database_pool_size: int = Field(default=5, env="DATABASE_POOL_SIZE", gt=0)
    
    # Secrets with sensitive=True are hidden in string representations
    admin_password: str = Field(default="", env="ADMIN_PASSWORD", sensitive=True)


# Load settings from environment variables and .env file
settings = AppSettings()
print(f"App name: {settings.app_name}")
print(f"Debug mode: {settings.debug}")
print(f"Database URL: {settings.database_url}")
```

Sample .env file:
```
APP_NAME=ProductionApp
DEBUG=true
API_SECRET_KEY=my-secret-key
DATABASE_URL=postgresql://user:password@localhost:5432/mydb
DATABASE_POOL_SIZE=10
ADMIN_PASSWORD=super-secret
```

### Settings Sources

You can customize settings sources and combine configuration from multiple places:

```python
import typing as t
from pathlib import Path
import json
import toml
from pydantic import Field
from pydantic_settings import (
    BaseSettings, 
    SettingsConfigDict,
    PydanticBaseSettingsSource,
    JsonConfigSettingsSource,
)


class MySettings(BaseSettings):
    """Settings with custom configuration sources"""
    
    model_config = SettingsConfigDict(
        env_prefix="MYAPP_",  # All env vars start with MYAPP_
        env_file=".env",      # Load from .env file
        json_file="config.json",  # Also load from JSON
    )
    
    name: str = "Default App"
    version: str = "0.1.0"
    features: list[str] = Field(default_factory=list)


# Create settings from multiple sources
# Precedence: environment variables > .env file > config.json > defaults
settings = MySettings()

# You can also override values at initialization
debug_settings = MySettings(name="Debug Build", features=["experimental"])
```

Example config.json:
```json
{
    "name": "My Application",
    "version": "1.2.3",
    "features": ["auth", "api", "export"]
}
```
