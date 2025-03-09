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

### Working with Advanced Types

Pydantic provides special handling for many complex types:

```python
import typing as t
from uuid import UUID
from datetime import datetime, date, time, timedelta
from decimal import Decimal
from ipaddress import IPv4Address, IPv6Address
from pathlib import Path
from pydantic import BaseModel, HttpUrl, EmailStr, SecretStr


class AdvancedTypes(BaseModel):
    """Example of various advanced types supported by Pydantic"""
    
    # Network types
    url: HttpUrl = "https://example.com"
    ip_v4: IPv4Address = "127.0.0.1"
    ip_v6: IPv6Address = "::1"
    
    # String types with validation
    email: EmailStr = "user@example.com"  # Requires email-validator package
    password: SecretStr = "secret123"  # Hidden in repr and serialization
    
    # Date & Time types
    created_at: datetime = datetime.now()
    birthday: date = date(1990, 1, 1)
    meeting_time: time = time(9, 30)
    duration: timedelta = timedelta(hours=1)
    
    # File system
    config_path: Path = Path("/etc/config.ini")
    
    # Other special types
    unique_id: UUID = "a6c18a4a-6987-4b6b-8d70-893e2b8c667c"
    price: Decimal = "19.99"  # High precision decimal


advanced = AdvancedTypes()
print(f"Email: {advanced.email}")
print(f"Password: {advanced.password}")  # Will print SecretStr('**********')
print(f"URL host: {advanced.url.host}")  # HttpUrl has properties like host, scheme, etc.
```

### Custom Types

Create your own custom types with validators:

```python
import typing as t
import re
from pydantic import (
    GetCoreSchemaHandler, 
    GetJsonSchemaHandler,
    BaseModel,
    ValidationError,
    AfterValidator, 
)
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import core_schema


# 1. Simple approach using Annotated
def validate_isbn(v: str) -> str:
    """Validate ISBN-10 or ISBN-13 format"""
    # Remove hyphens and spaces
    isbn = re.sub(r'[\s-]', '', v)
    
    # Validate ISBN-10
    if len(isbn) == 10 and isbn[:9].isdigit() and (isbn[9].isdigit() or isbn[9].lower() == 'x'):
        return isbn
    
    # Validate ISBN-13
    if len(isbn) == 13 and isbn.isdigit() and isbn.startswith(('978', '979')):
        return isbn
    
    raise ValueError("Invalid ISBN format")


# Create a custom ISBN type using Annotated
ISBN = t.Annotated[str, AfterValidator(validate_isbn)]


# 2. More complex approach with custom type
class PostalCode(str):
    """Custom type for postal code validation"""

    @classmethod
    def __get_validators__(cls):
        # For backwards compatibility with Pydantic v1
        yield cls.validate
        
    @classmethod
    def __get_pydantic_core_schema__(
        cls, _source_type: t.Any, _handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        """Define the core schema for validation"""
        return core_schema.with_info_schema(
            core_schema.str_schema(),
            serialization=core_schema.str_serializer(),
            validator=cls.validate,
            type=cls,
        )
    
    @classmethod
    def validate(cls, value: str) -> 'PostalCode':
        """Validate postal code format"""
        if not isinstance(value, str):
            raise ValueError("Postal code must be a string")
            
        # Remove spaces
        postal_code = value.strip().replace(" ", "")
        
        # Simple validation - should be customized for your country
        if len(postal_code) < 3 or len(postal_code) > 10:
            raise ValueError("Invalid postal code length")
            
        if not re.match(r'^[a-zA-Z0-9]+$', postal_code):
            raise ValueError("Postal code should contain only letters and numbers")
            
        # Return a new instance of the custom type
        return cls(postal_code)
    
    @classmethod
    def __get_json_schema__(
        cls, _source_type: t.Any, _handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        """Define JSON schema for the custom type"""
        return {
            "type": "string",
            "format": "postal-code",
            "pattern": "^[a-zA-Z0-9]{3,10}$",
            "description": "Postal/ZIP code in standard format",
        }


# 3. Using the custom types
class Book(BaseModel):
    title: str
    isbn: ISBN
    

class Address(BaseModel):
    street: str
    city: str
    postal_code: PostalCode
    country: str


# Test the custom types
try:
    book = Book(title="Python Programming", isbn="978-0-13-475759-9")
    print(f"Valid ISBN: {book.isbn}")
    
    address = Address(
        street="123 Main St",
        city="Anytown",
        postal_code="AB12 3CD",
        country="UK"
    )
    print(f"Valid postal code: {address.postal_code}")
except ValidationError as e:
    print(f"Validation error: {e}")
```

### Protocol Validation

Pydantic supports validation against protocols (structural typing):

```python
import typing as t
from typing_extensions import Protocol, runtime_checkable
from pydantic import TypeAdapter, ValidationError


# Define a protocol - a structural interface
@runtime_checkable
class Drivable(Protocol):
    """Protocol for objects that can be driven"""
    def drive(self) -> str: ...
    speed: int


# Classes that structurally match the protocol
class Car:
    speed: int = 120
    
    def __init__(self, make: str):
        self.make = make
    
    def drive(self) -> str:
        return f"Driving {self.make} at {self.speed} km/h"


class Bicycle:
    speed: int = 25
    
    def drive(self) -> str:
        return f"Pedaling at {self.speed} km/h"


class Plane:
    altitude: int = 10000
    
    def fly(self) -> str:
        return f"Flying at {self.altitude} feet"


# Validate against the protocol
drivable_adapter = TypeAdapter(Drivable)

# These conform to the Drivable protocol
car = drivable_adapter.validate_python(Car("Toyota"))
bicycle = drivable_adapter.validate_python(Bicycle())

try:
    # This will fail - Plane doesn't implement drive()
    plane = drivable_adapter.validate_python(Plane())
except ValidationError as e:
    print(f"Validation error: {e}")
```

### Dynamic Model Generation

Create Pydantic models dynamically at runtime:

```python
import typing as t
from pydantic import create_model, BaseModel, Field


# Function to generate a model dynamically
def create_product_model(category: str, fields: dict[str, tuple[t.Type, t.Any]]) -> t.Type[BaseModel]:
    """
    Dynamically create a product model based on category and fields.
    
    Args:
        category: Product category name
        fields: Dictionary mapping field names to (type, default) tuples
    
    Returns:
        A new Pydantic model class
    """
    # Common fields for all products
    common_fields = {
        "id": (int, Field(..., description="Product ID")),
        "name": (str, Field(..., min_length=1, max_length=100)),
        "category": (str, Field(category, description="Product category")),
        "price": (float, Field(..., gt=0)),
    }
    
    # Combine common fields with category-specific fields
    all_fields = {**common_fields, **fields}
    
    # Create and return the model
    return create_model(
        f"{category.title()}Product",
        **all_fields,
        __doc__=f"Dynamically generated model for {category} products"
    )


# Create different product models
ElectronicProduct = create_product_model(
    "electronic",
    {
        "warranty_months": (int, Field(12, ge=0)),
        "voltage": (float, Field(220.0)),
        "has_bluetooth": (bool, Field(False)),
    }
)

ClothingProduct = create_product_model(
    "clothing",
    {
        "size": (str, Field(..., pattern=r'^(XS|S|M|L|XL|XXL)$')),
        "color": (str, Field(...)),
        "material": (str, Field("cotton")),
    }
)

# Use the dynamically generated models
laptop = ElectronicProduct(
    id=1001,
    name="Laptop Pro",
    price=1299.99,
    warranty_months=24,
    voltage=110.0,
    has_bluetooth=True
)

shirt = ClothingProduct(
    id=2001,
    name="Summer Shirt",
    price=29.99,
    size="M",
    color="Blue"
)

# Access fields normally
print(f"{laptop.name}: ${laptop.price} with {laptop.warranty_months} months warranty")
print(f"{shirt.name}: ${shirt.price}, Size: {shirt.size}, Material: {shirt.material}")

# Generate schema for dynamic models
print(ElectronicProduct.model_json_schema()["title"])  # "ElectronicProduct"
```

## Pydantic Ecosystem

### Plugins and Extensions

Pydantic offers a rich ecosystem of plugins and extensions:

```python
import typing as t
from pydantic import BaseModel, Field
from pydantic_extra_types.phone_numbers import PhoneNumber
from pydantic_extra_types.color import Color
from pydantic_extra_types.country import Country, CountryInfo


class Contact(BaseModel):
    """Example using Pydantic extension packages"""
    name: str
    # From pydantic-extra-types
    phone: PhoneNumber = Field(..., description="Phone number with international format")
    country: Country = Field(..., description="ISO 3166-1 alpha-2 country code")
    favorite_color: Color = Field(
        default="blue", 
        description="Color in any common format (name, hex, rgb, etc.)"
    )
    
    def get_country_info(self) -> CountryInfo:
        """Get detailed information about the contact's country"""
        return self.country.info


# Create a contact with various formats
contact = Contact(
    name="John Smith",
    phone="+1-555-123-4567",
    country="US",
    favorite_color="#00FF00"  # hex green
)

# Accessing validated data
print(f"Name: {contact.name}")
print(f"Phone: {contact.phone}")  # Normalized format
print(f"Country: {contact.country.name}")  # Full country name
print(f"Favorite color: {contact.favorite_color.as_hex()}")
print(f"Color as RGB: {contact.favorite_color.as_rgb()}")

# Get additional country information
country_info = contact.get_country_info()
print(f"Currency: {country_info.currency}")
print(f"Capital: {country_info.capital}")
```

### Common Plugin Packages

- **pydantic-settings**: Settings management with environment variables support
- **pydantic-extra-types**: Additional types like phone numbers, payment cards, etc.
- **pydantic-factories**: Testing utilities for generating fake data
- **pydantic-mongo**: MongoDB ODM based on Pydantic models
- **pydantic-yaml**: YAML support for Pydantic models

### Integration with FastAPI

Pydantic is the foundation of FastAPI's request validation and documentation:

```python
from fastapi import FastAPI, Path, Query, Body, HTTPException
from pydantic import BaseModel, Field, EmailStr, ValidationError

# Define models for API
class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    full_name: str = Field(None, max_length=100)
    password: str = Field(..., min_length=8)


class UserResponse(BaseModel):
    id: int
    username: str
    email: EmailStr
    full_name: str | None = None


# Create FastAPI app
app = FastAPI(title="User API", description="API with Pydantic validation")


@app.post("/users/", response_model=UserResponse)
async def create_user(user: UserCreate) -> UserResponse:
    """
    Create a new user with validation:
    
    - Username must be 3-50 characters
    - Email must be valid format
    - Password must be at least 8 characters
    """
    # Pydantic already validated the input
    # We can safely access validated, correctly typed data
    return UserResponse(
        id=123,
        username=user.username,
        email=user.email,
        full_name=user.full_name
    )


@app.get("/users/{user_id}")
async def get_user(
    user_id: int = Path(..., title="User ID", gt=0),
    include_settings: bool = Query(False, title="Include user settings")
) -> UserResponse:
    """Get user by ID"""
    # Path and Query parameters validated by Pydantic
    if user_id != 123:
        raise HTTPException(status_code=404, detail="User not found")
        
    return UserResponse(
        id=user_id,
        username="johndoe",
        email="john@example.com"
    )
```

## Learning Resources

- [Official Documentation](https://docs.pydantic.dev/)
- [GitHub Repository](https://github.com/pydantic/pydantic)
- [FastAPI Documentation](https://fastapi.tiangolo.com/) (includes many Pydantic examples)
- [Pydantic Discord Community](https://discord.gg/FXtYdGTRF4)

## Conclusion

Pydantic v2 offers a powerful, flexible and high-performance way to validate, serialize, and document your data models using Python's type system. Key benefits include:

- Type-driven validation using standard Python type annotations
- Exceptional performance via Rust-based validation engine
- Flexible configuration options for various use cases
- Rich ecosystem of integrations and extensions
- Comprehensive JSON Schema generation

Whether you're building APIs with FastAPI, validating configuration settings, or just need robust data validation in your Python application, Pydantic provides an elegant solution that works with your IDE and type checker while ensuring runtime data correctness.
