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

Since v2.10+, TypeAdapters support deferred schema building and manual rebuilds. This is particularly useful for:

1. Types with circular or forward references
2. Types where core schema builds are expensive
3. Situations where types need to be modified after TypeAdapter creation

When `defer_build=True` is set in the config, Pydantic will not immediately build the schema, but wait until the first time validation or serialization is needed, or until you manually call `.rebuild()`.

```python
# Deferring build for expensive schema generation
complex_type_adapter = TypeAdapter(
    dict[str, list[tuple[int, float, str]]],
    ConfigDict(defer_build=True)
)

# Build the schema manually when needed
complex_type_adapter.rebuild()

# Now perform validation
data = complex_type_adapter.validate_python({"key": [(1, 1.5, "value")]})
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

## Error Handling

Pydantic provides comprehensive error handling mechanisms to help you understand and manage validation issues.

### ValidationError

Most validation failures raise `ValidationError` which contains detailed information about what went wrong:

```python
import typing as t
from pydantic import BaseModel, ValidationError, Field


class User(BaseModel):
    username: str = Field(min_length=3)
    password: str = Field(min_length=8)
    age: int = Field(gt=0, lt=120)


try:
    # Multiple validation errors
    User(username="a", password="123", age=-5)
except ValidationError as e:
    # Access the errors
    print(f"Error count: {len(e.errors())}")
    
    # Print pretty formatted error
    print(e)
    
    # Get JSON representation of errors
    json_errors = e.json()
    
    # Get error details
    for error in e.errors():
        print(f"Field: {'.'.join(error['loc'])}")
        print(f"Error type: {error['type']}")
        print(f"Message: {error['msg']}")
```

### Working with Error Messages

You can customize error messages and access errors in structured ways:

```python
import typing as t
from pydantic import BaseModel, Field, model_validator, ValidationError


class SignupForm(BaseModel):
    username: str = Field(min_length=3, description="Username for the account")
    password1: str = Field(min_length=8)
    password2: str
    
    @model_validator(mode='after')
    def passwords_match(self) -> 'SignupForm':
        if self.password1 != self.password2:
            # Custom error using ValueError
            raise ValueError("Passwords don't match")
        return self


try:
    SignupForm(username="user", password1="password123", password2="different")
except ValidationError as e:
    # Get a mapping of field name to error messages
    error_map = {'.'.join(err['loc']): err['msg'] for err in e.errors()}
    
    # Now you can access errors by field name
    if '__root__' in error_map:
        print(f"Form error: {error_map['__root__']}")
    
    if 'username' in error_map:
        print(f"Username error: {error_map['username']}")
        
    # Or render form with errors
    for field, error in error_map.items():
        print(f"<div class='error'>{field}: {error}</div>")
```

### Handling Errors in API Contexts

When working with frameworks like FastAPI, ValidationError is automatically caught and converted to appropriate HTTP responses:

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, ValidationError

app = FastAPI()

class Item(BaseModel):
    name: str = Field(min_length=3)
    price: float = Field(gt=0)


@app.post("/items/")
async def create_item(item_data: dict):
    try:
        # Manual validation of dictionary data
        item = Item.model_validate(item_data)
        return {"status": "success", "item": item}
    except ValidationError as e:
        # Convert to HTTP exception
        raise HTTPException(
            status_code=422,
            detail=e.errors(),
        )
```

### Custom Error Types

You can create custom error types and error handlers:

```python
import typing as t
from pydantic import BaseModel, field_validator, ValidationInfo


class CustomValidationError(Exception):
    """Custom validation error with additional context"""
    def __init__(self, field: str, message: str, context: dict = None):
        self.field = field
        self.message = message
        self.context = context or {}
        super().__init__(f"{field}: {message}")


class PaymentCard(BaseModel):
    card_number: str
    expiry_date: str
    
    @field_validator('card_number')
    @classmethod
    def validate_card_number(cls, v: str, info: ValidationInfo) -> str:
        # Remove spaces
        v = v.replace(' ', '')
        
        # Simple validation for demonstration
        if not v.isdigit():
            raise CustomValidationError(
                field='card_number',
                message='Card number must contain only digits',
                context={'raw_value': v}
            )
            
        if len(v) not in (13, 15, 16):
            raise CustomValidationError(
                field='card_number', 
                message='Invalid card number length',
                context={'length': len(v)}
            )
            
        return v


# Handler for custom errors
def process_payment(payment_data: dict) -> dict:
    try:
        card = PaymentCard.model_validate(payment_data)
        return {"status": "success", "card": card.model_dump()}
    except CustomValidationError as e:
        return {
            "status": "error",
            "field": e.field,
            "message": e.message,
            "context": e.context
        }
    except ValidationError as e:
        return {"status": "error", "errors": e.errors()}


# Usage
result = process_payment({"card_number": "4111 1111 1111 111", "expiry_date": "12/24"})
print(result)
# {'status': 'error', 'field': 'card_number', 'message': 'Invalid card number length', 'context': {'length': 15}}
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

w1 = Wrong()
w2 = Wrong()
w1.tags.append("item")
print(w2.tags)  # ['item'] - w2 is affected by change to w1!


# CORRECT: Use Field with default_factory
class Correct(BaseModel):
    tags: list[str] = Field(default_factory=list)  # Each instance gets its own list

c1 = Correct()
c2 = Correct()
c1.tags.append("item")
print(c2.tags)  # [] - c2 has its own separate list
```

This applies to all mutable types: `list`, `dict`, `set`, etc. Always use `default_factory` for mutable defaults.

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

#### Advanced Performance Tips

For maximum performance in Pydantic v2:

1. **Reuse Type Adapters**: Creating a TypeAdapter has overhead from analyzing types and building schemas. Create them once and reuse.

    ```python
    # WRONG: Creating TypeAdapter in a loop
    def process_items(items_data: list[dict]) -> list:
        processed = []
        for item_data in items_data:
            adapter = TypeAdapter(Item)  # Expensive! Created repeatedly
            processed.append(adapter.validate_python(item_data))
        return processed
    
    # RIGHT: Create once, reuse many times
    ITEM_ADAPTER = TypeAdapter(Item)  # Create once
    
    def process_items(items_data: list[dict]) -> list:
        return [ITEM_ADAPTER.validate_python(item) for item_data in items_data]
    ```

2. **Use direct core mode access**: In ultra-performance-critical code, you can use core mode:

    ```python
    from pydantic_core import SchemaValidator, core_schema
    
    # Direct core schema creation for maximum performance
    schema = core_schema.dict_schema(
        keys_schema=core_schema.str_schema(),
        values_schema=core_schema.int_schema()
    )
    validator = SchemaValidator(schema)
    
    # Using the validator directly
    result = validator.validate_python({"key1": 1, "key2": "2"})
    # {"key1": 1, "key2": 2}
    ```

3. **Avoid unnecessary model creations**: Use `model_construct` when data is already validated, or validate collections in bulk:

    ```python
    # Bulk validation of multiple items at once (one schema traversal)
    items_adapter = TypeAdapter(list[Item])
    validated_items = items_adapter.validate_python(items_data)
    ```

4. **Prefer concrete types**: Concrete types like `list` and `dict` have faster validation than abstract types like `Sequence` or `Mapping`.

5. **Use frozen models** for immutable data:

    ```python
    class Config(BaseModel, frozen=True):
        api_key: str
        timeout: int = 60
    ```

6. **Disable validation when appropriate**: For trusted input, you can skip validation with `model_construct` or bypass it with direct attribute assignment when appropriate:

    ```python
    # For trusted data that doesn't need validation
    user = User.model_construct(**trusted_data)
    ```

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

## Real-world Examples

Here are several practical examples of how to use Pydantic in common scenarios.

### Configuration System

Create a robust configuration system with environment variable support:

```python
import typing as t
from pathlib import Path
import os
from functools import lru_cache
from pydantic import Field, SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """Database connection settings with defaults and validation."""
    model_config = SettingsConfigDict(env_prefix="DB_")
    
    host: str = "localhost"
    port: int = 5432
    user: str = "postgres"
    password: SecretStr = Field(default=SecretStr(""))
    name: str = "app"
    pool_size: int = Field(default=5, gt=0, le=20)
    
    @property
    def url(self) -> str:
        """Construct the database URL from components."""
        return f"postgresql://{self.user}:{self.password.get_secret_value()}@{self.host}:{self.port}/{self.name}"


class LoggingSettings(BaseSettings):
    """Logging configuration."""
    model_config = SettingsConfigDict(env_prefix="LOG_")
    
    level: t.Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file: t.Optional[Path] = None


class AppSettings(BaseSettings):
    """Main application settings."""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    
    app_name: str = "MyApp"
    version: str = "0.1.0"
    debug: bool = False
    secret_key: SecretStr = Field(...)  # Required field
    allowed_hosts: list[str] = Field(default_factory=lambda: ["localhost", "127.0.0.1"])
    
    # Nested settings
    db: DatabaseSettings = Field(default_factory=DatabaseSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)


# Use lru_cache to avoid loading settings multiple times
@lru_cache()
def get_settings() -> AppSettings:
    """Load settings from environment with caching."""
    try:
        return AppSettings()
    except ValidationError as e:
        print(f"Settings validation error: {e}")
        raise


# Usage in the application
def main():
    settings = get_settings()
    print(f"Starting {settings.app_name} v{settings.version}")
    print(f"Database URL: {settings.db.url}")
    print(f"Log level: {settings.logging.level}")


if __name__ == "__main__":
    main()
```

### REST API Request/Response Models

Organize API models for clean separation of concerns:

```python
import typing as t
from datetime import datetime
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, EmailStr, model_validator, field_validator


# Base models with common fields
class UserBase(BaseModel):
    """Common user fields"""
    email: EmailStr
    username: str = Field(min_length=3, max_length=50)


# Input models (for API requests)
class UserCreate(UserBase):
    """Data needed to create a new user"""
    password: str = Field(min_length=8)
    password_confirm: str
    
    @model_validator(mode='after')
    def check_passwords_match(self) -> 'UserCreate':
        if self.password != self.password_confirm:
            raise ValueError("Passwords do not match")
        return self


class UserUpdate(BaseModel):
    """Data for updating user profile (all fields optional)"""
    email: t.Optional[EmailStr] = None
    username: t.Optional[str] = Field(None, min_length=3, max_length=50)


# Output models (for API responses)
class UserRead(UserBase):
    """User data returned from API"""
    id: UUID
    is_active: bool
    created_at: datetime
    updated_at: t.Optional[datetime] = None


class UserList(BaseModel):
    """Paginated list of users"""
    items: list[UserRead]
    total: int
    page: int
    size: int
    
    @property
    def pages(self) -> int:
        """Calculate total pages based on items and page size"""
        return (self.total + self.size - 1) // self.size


# Internal models (for database operations)
class UserInDB(UserRead):
    """User model with password hash for internal use"""
    hashed_password: str
    
    @classmethod
    def from_create(cls, user_create: UserCreate, password_hash: str) -> 'UserInDB':
        """Create internal user from registration data"""
        return cls(
            id=uuid4(),
            email=user_create.email,
            username=user_create.username,
            hashed_password=password_hash,
            is_active=True,
            created_at=datetime.now()
        )


# FastAPI example usage
from fastapi import FastAPI, HTTPException, Depends

app = FastAPI()

# Mock database
users_db = {}

# Dependencies
def get_user_by_id(user_id: UUID) -> UserInDB:
    if user_id not in users_db:
        raise HTTPException(status_code=404, detail="User not found")
    return users_db[user_id]


@app.post("/users/", response_model=UserRead)
async def create_user(user_data: UserCreate):
    # Hash the password (in a real app, use proper hashing)
    hashed_password = f"hashed_{user_data.password}"
    
    # Create user in DB
    user = UserInDB.from_create(user_data, hashed_password)
    users_db[user.id] = user
    
    # Return user without hashed_password
    return user


@app.get("/users/{user_id}", response_model=UserRead)
async def read_user(user: UserInDB = Depends(get_user_by_id)):
    return user


@app.patch("/users/{user_id}", response_model=UserRead)
async def update_user(update_data: UserUpdate, user: UserInDB = Depends(get_user_by_id)):
    # Update user with provided data, ignoring None values
    user_data = user.model_dump()
    update_dict = update_data.model_dump(exclude_unset=True, exclude_none=True)
    
    # Handle password separately
    if 'password' in update_dict:
        update_dict['hashed_password'] = f"hashed_{update_dict.pop('password')}"
    
    # Update the user data
    updated_user_data = {**user_data, **update_dict, 'updated_at': datetime.now()}
    updated_user = UserInDB.model_validate(updated_user_data)
    users_db[user.id] = updated_user
    
    return updated_user
```

### Data Processing Pipeline

Use Pydantic in a data processing pipeline for validation and transformation:

```python
import typing as t
from datetime import datetime, date
from enum import Enum
from pydantic import BaseModel, Field, ValidationError, field_validator, TypeAdapter


# Input data models
class DataSource(str, Enum):
    CSV = "csv"
    API = "api"
    DATABASE = "db"


class RawDataPoint(BaseModel):
    timestamp: str
    temperature: t.Any  # Could be string or number
    humidity: t.Any
    pressure: t.Any
    location_id: str
    source: DataSource
    
    @field_validator('timestamp')
    @classmethod
    def validate_timestamp(cls, v: str) -> str:
        # Basic timestamp format validation
        formats = ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"]
        for fmt in formats:
            try:
                datetime.strptime(v, fmt)
                return v
            except ValueError:
                continue
        raise ValueError("Invalid timestamp format")


# Processed data model
class ProcessedDataPoint(BaseModel):
    timestamp: datetime
    date: date
    temperature: float = Field(ge=-50.0, le=100.0)  # Celsius
    humidity: float = Field(ge=0.0, le=100.0)  # Percentage
    pressure: float = Field(ge=800.0, le=1200.0)  # hPa
    location_id: str
    source: DataSource
    
    @classmethod
    def from_raw(cls, raw: RawDataPoint) -> 'ProcessedDataPoint':
        """Convert raw data to processed format with type conversion."""
        timestamp = datetime.strptime(
            raw.timestamp, 
            "%Y-%m-%dT%H:%M:%S" if "T" in raw.timestamp else "%Y-%m-%d %H:%M:%S"
        )
        
        return cls(
            timestamp=timestamp,
            date=timestamp.date(),
            temperature=float(raw.temperature),
            humidity=float(raw.humidity),
            pressure=float(raw.pressure),
            location_id=raw.location_id,
            source=raw.source
        )


# Processing pipeline
class DataProcessor:
    def __init__(self):
        # Create adapter once for performance
        self.raw_adapter = TypeAdapter(list[RawDataPoint])
        
    def process_batch(self, raw_data: list[dict]) -> dict[str, t.Any]:
        """Process a batch of raw data points."""
        start_time = datetime.now()
        result = {
            "processed": 0,
            "errors": 0,
            "error_details": [],
            "processed_data": []
        }
        
        try:
            # Validate all raw data points at once
            validated_raw = self.raw_adapter.validate_python(raw_data)
            
            # Process each point
            for raw_point in validated_raw:
                try:
                    processed = ProcessedDataPoint.from_raw(raw_point)
                    result["processed_data"].append(processed.model_dump())
                    result["processed"] += 1
                except ValidationError as e:
                    result["errors"] += 1
                    result["error_details"].append({
                        "raw_data": raw_point.model_dump(),
                        "error": e.errors()
                    })
                    
        except ValidationError as e:
            result["errors"] = len(raw_data)
            result["error_details"].append({"error": "Batch validation failed", "details": e.errors()})
            
        result["processing_time"] = (datetime.now() - start_time).total_seconds()
        return result



# Usage
processor = DataProcessor()

# Sample data batch
sample_data = [
    {
        "timestamp": "2023-09-15T12:30:45",
        "temperature": "22.5",
        "humidity": "65",
        "pressure": "1013.2",
        "location_id": "sensor-001",
        "source": "csv"
    },
    {
        "timestamp": "2023-09-15 12:45:00",
        "temperature": 23.1,
        "humidity": 64.5,
        "pressure": 1012.8,
        "location_id": "sensor-002",
        "source": "api"
    },
    # Invalid data point to demonstrate error handling
    {
        "timestamp": "invalid-date",
        "temperature": "too hot",
        "humidity": 200,  # Out of range
        "pressure": "1010",
        "location_id": "sensor-003",
        "source": "db"
    }
]

# Process the batch
result = processor.process_batch(sample_data)
print(f"Processed: {result['processed']}, Errors: {result['errors']}")
```

### Domain-Driven Design with Pydantic

Structure your domain models cleanly with Pydantic:

```python
import typing as t
from datetime import datetime
from uuid import UUID, uuid4
from decimal import Decimal
from enum import Enum
from pydantic import BaseModel, Field, computed_field, model_validator


# Value objects
class Money(BaseModel):
    """Value object representing an amount in a specific currency."""
    amount: Decimal = Field(ge=0)
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")
    
    def __add__(self, other: 'Money') -> 'Money':
        if not isinstance(other, Money) or self.currency != other.currency:
            raise ValueError(f"Cannot add {self.currency} and {other.currency}")
        return Money(amount=self.amount + other.amount, currency=self.currency)
    
    def __mul__(self, quantity: int) -> 'Money':
        return Money(amount=self.amount * quantity, currency=self.currency)
    
    def __str__(self) -> str:
        return f"{self.amount:.2f} {self.currency}"


class Address(BaseModel):
    """Value object for addresses."""
    street: str
    city: str
    state: str
    postal_code: str
    country: str = "USA"


# Enums
class OrderStatus(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


# Entities
class ProductId(str):
    """Strong type for product IDs."""
    pass


class Product(BaseModel):
    """Product entity."""
    id: ProductId
    name: str
    description: str
    price: Money
    weight_kg: float = Field(gt=0)
    in_stock: int = Field(ge=0)
    
    @computed_field
    def is_available(self) -> bool:
        return self.in_stock > 0


class OrderItem(BaseModel):
    """Line item in an order."""
    product_id: ProductId
    product_name: str
    unit_price: Money
    quantity: int = Field(gt=0)
    
    @computed_field
    def total_price(self) -> Money:
        return self.unit_price * self.quantity


class Order(BaseModel):
    """Order aggregate root."""
    id: UUID = Field(default_factory=uuid4)
    customer_id: UUID
    items: list[OrderItem] = Field(default_factory=list)
    shipping_address: Address
    billing_address: t.Optional[Address] = None
    status: OrderStatus = OrderStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: t.Optional[datetime] = None
    
    # Business logic
    @model_validator(mode='after')
    def set_billing_address(self) -> 'Order':
        """Default billing address to shipping address if not provided."""
        if self.billing_address is None:
            self.billing_address = self.shipping_address
        return self
    
    @computed_field
    def total_amount(self) -> Money:
        """Calculate the total order amount."""
        if not self.items:
            return Money(amount=Decimal('0'))
        
        # Start with the first item's total and currency
        total = self.items[0].total_price
        
        # Add remaining items (if any)
        for item in self.items[1:]:
            total += item.total_price
            
        return total
    
    def add_item(self, item: OrderItem) -> None:
        """Add an item to the order."""
        if self.status != OrderStatus.PENDING:
            raise ValueError(f"Cannot modify order in {self.status} status")
        self.items.append(item)
        self.updated_at = datetime.now()
    
    def update_status(self, new_status: OrderStatus) -> None:
        """Update the order status."""
        # Validate status transitions
        valid_transitions = {
            OrderStatus.PENDING: {OrderStatus.PAID, OrderStatus.CANCELLED},
            OrderStatus.PAID: {OrderStatus.SHIPPED, OrderStatus.CANCELLED},
            OrderStatus.SHIPPED: {OrderStatus.DELIVERED},
            OrderStatus.DELIVERED: set(),
            OrderStatus.CANCELLED: set()
        }
        
        if new_status not in valid_transitions[self.status]:
            raise ValueError(
                f"Invalid status transition from {self.status} to {new_status}"
            )
            
        self.status = new_status
        self.updated_at = datetime.now()


# Usage
def create_sample_order() -> Order:
    # Create products
    product1 = Product(
        id=ProductId("PROD-001"),
        name="Mechanical Keyboard",
        description="Tactile mechanical keyboard with RGB lighting",
        price=Money(amount=Decimal("99.99")),
        weight_kg=1.2,
        in_stock=10
    )
    
    product2 = Product(
        id=ProductId("PROD-002"),
        name="Wireless Mouse",
        description="Ergonomic wireless mouse",
        price=Money(amount=Decimal("45.50")),
        weight_kg=0.3,
        in_stock=20
    )
    
    # Create order items
    item1 = OrderItem(
        product_id=product1.id,
        product_name=product1.name,
        unit_price=product1.price,
        quantity=1
    )
    
    item2 = OrderItem(
        product_id=product2.id,
        product_name=product2.name,
        unit_price=product2.price,
        quantity=2
    )
    
    # Create the order
    order = Order(
        customer_id=uuid4(),
        shipping_address=Address(
            street="123 Main St",
            city="Anytown",
            state="CA",
            postal_code="12345",
            country="USA"
        ),
        items=[item1, item2]
    )
    
    return order


# Demo
order = create_sample_order()
print(f"Order ID: {order.id}")
print(f"Total: {order.total_amount}")
print(f"Initial status: {order.status}")

# Process order
order.update_status(OrderStatus.PAID)
print(f"New status: {order.status}")

# Try invalid transition
try:
    order.update_status(OrderStatus.PENDING)
except ValueError as e:
    print(f"Error: {e}")
```

## Learning Resources

- [Official Documentation](https://docs.pydantic.dev/)
- [GitHub Repository](https://github.com/pydantic/pydantic)
- [FastAPI Documentation](https://fastapi.tiangolo.com/) (includes many Pydantic examples)
- [Pydantic Discord Community](https://discord.gg/FXtYdGTRF4)

## Conclusion

Pydantic v2 offers a powerful, flexible and high-performance way to validate, serialize, and document your data models using Python's type system. Key benefits include:

- **Type-driven validation**: Use standard Python type annotations for schema definition
- **Exceptional performance**: Rust-based validation engine provides up to 100x faster validation compared to v1
- **Flexible coercion and strictness**: Toggle strict mode globally or per field
- **Extensive validation tools**: Field validators, model validators, custom types
- **Comprehensive serialization**: To dictionaries, JSON, with custom options
- **TypeAdapters**: Validate data against any Python type without creating models
- **Rich ecosystem**: Integrates with FastAPI, Django, testing frameworks, and more

In practice, Pydantic v2 excels in a wide range of scenarios including:

- API schema validation with web frameworks like FastAPI
- Configuration management with pydantic-settings
- Data processing pipelines
- Domain-driven design with rich model semantics
- Database ORM integration

This document covers the fundamentals through advanced uses of Pydantic v2, including:

- Basic model definition and validation
- Field customization and constraints
- Validation with custom validators
- Serialization options
- Type adapters
- JSON Schema generation
- Error handling strategies
- Performance optimization
- Common pitfalls and solutions
- Real-world examples and patterns

Whether you're building robust APIs, data processing pipelines, or validating configuration, Pydantic provides an elegant solution that works with your IDE and type checker while ensuring runtime data correctness.

## Experimental Features

Pydantic includes experimental features that may become permanent in future versions. These features are subject to change or removal and will show a warning when imported.

### Suppressing Experimental Warnings

```python
import warnings
from pydantic import PydanticExperimentalWarning

warnings.filterwarnings('ignore', category=PydanticExperimentalWarning)
```

### Pipeline API

The Pipeline API (introduced in v2.8.0) allows composing validation, constraints, and transformations in a more type-safe manner:

```python
from datetime import datetime
from typing import Annotated
from pydantic import BaseModel, Field
from pydantic.experimental import pipeline

# Define transformations
def to_lowercase(v: str) -> str:
    return v.lower()

def normalize_email(v: str) -> str:
    username, domain = v.split('@')
    username = username.replace('.', '')
    return f"{username}@{domain}"

def to_adult_status(birth_date: datetime) -> bool:
    age = (datetime.now() - birth_date).days / 365.25
    return age >= 18

# Define a model with pipeline transformations
class User(BaseModel):
    username: Annotated[
        str, 
        pipeline.transform(to_lowercase),
        Field(min_length=3)
    ]
    email: Annotated[
        str,
        pipeline.validate(str),  # Validate as string first
        pipeline.transform(normalize_email),  # Then transform
        pipeline.predicate(lambda v: '@' in v, "Invalid email format")  # Check condition
    ]
    birth_date: datetime
    is_adult: Annotated[bool, pipeline.computed(to_adult_status, dependencies=['birth_date'])]

# Usage
user = User(
    username="JohnDoe",  # Will be converted to lowercase
    email="john.doe@example.com",  # Will be normalized
    birth_date="1990-01-01T00:00:00"
)

print(user.username)  # johndoe
print(user.email)  # johndoe@example.com
print(user.is_adult)  # True or False depending on current date
```

This API provides better type safety and allows more complex validation flows than traditional validators.
