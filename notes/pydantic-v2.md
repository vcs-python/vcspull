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
