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

#### JSON Schema Modes

Pydantic v2 supports two JSON schema modes that control how the schema is generated:

```python
from decimal import Decimal
from pydantic import BaseModel

class Price(BaseModel):
    amount: Decimal

# Validation schema - includes all valid input formats
validation_schema = Price.model_json_schema(mode='validation')
# {
#   "properties": {
#     "amount": {
#       "anyOf": [{"type": "number"}, {"type": "string"}],
#       "title": "Amount"
#     }
#   },
#   "required": ["amount"],
#   "title": "Price",
#   "type": "object"
# }

# Serialization schema - only includes output format
serialization_schema = Price.model_json_schema(mode='serialization')
# {
#   "properties": {
#     "amount": {"type": "string", "title": "Amount"}
#   },
#   "required": ["amount"],
#   "title": "Price",
#   "type": "object"
# }
```

#### Advanced Schema Customization

For more complex schema customization, you can also:

1. **Use `json_schema_extra` in `Field()`**:
   ```python
   website: str = Field(
       json_schema_extra={
           "format": "uri",
           "pattern": "^https?://",
           "examples": ["https://example.com"]
       }
   )
   ```

2. **Add custom keywords with model_config**:
   ```python
   model_config = ConfigDict(
       json_schema_extra={
           "$comment": "This schema is for internal use only.",
           "additionalProperties": False
       }
   )
   ```

3. **Use the ref_template parameter** to control how references are generated:
   ```python
   # Use full paths in references
   schema = model.model_json_schema(ref_template="#/$defs/{model}")
   
   # Inline all references (no $refs)
   schema = model.model_json_schema(ref_template="{model}")
   ```

4. **Generate schema from TypeAdapter**:
   ```python
   from pydantic import TypeAdapter
   
   ListOfUsers = TypeAdapter(list[User])
   schema = ListOfUsers.json_schema()
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

#### Computed Field Options

The `@computed_field` decorator accepts several parameters to customize its behavior:

```python
from datetime import datetime
from functools import cached_property
from pydantic import BaseModel, computed_field


class Rectangle(BaseModel):
    width: float
    height: float
    
    @computed_field(
        alias="area_sq_m",         # Custom alias for serialization
        title="Area",              # JSON schema title
        description="Area in m²",  # JSON schema description
        repr=True,                 # Include in string representation
        examples=[25.0, 36.0],     # Examples for JSON schema
    )
    @property
    def area(self) -> float:
        return self.width * self.height
    
    @computed_field(repr=False)    # Exclude from string representation
    @cached_property               # Use cached_property for performance
    def perimeter(self) -> float:
        return 2 * (self.width + self.height)


# Create an instance
rect = Rectangle(width=5, height=10)
print(rect)             # Rectangle(width=5.0, height=10.0, area=50.0)
print(rect.perimeter)   # 30.0 (cached after first access)
print(rect.model_dump()) 
# {'width': 5.0, 'height': 10.0, 'area': 50.0, 'perimeter': 30.0}

# Customized serialization with alias
print(rect.model_dump(by_alias=True))
# {'width': 5.0, 'height': 10.0, 'area_sq_m': 50.0, 'perimeter': 30.0}

# JSON schema includes computed fields in serialization mode
print(Rectangle.model_json_schema(mode='serialization'))
# Output includes 'area' and 'perimeter' fields
```

#### Important Notes on Computed Fields

1. **Property vs. Method**: The `@computed_field` decorator converts methods to properties if they aren't already.

2. **Type Hinting**: Always provide return type annotations for proper JSON schema generation.

3. **With cached_property**: Use `@cached_property` for expensive calculations (apply it before `@computed_field`).

4. **Readonly in Schema**: Computed fields are marked as `readOnly: true` in JSON schema.

5. **Field Dependencies**: Computed fields depend on other fields but these dependencies aren't tracked automatically.

6. **Deprecating Computed Fields**: You can mark computed fields as deprecated:
   ```python
   from typing_extensions import deprecated
   
   @computed_field
   @property
   @deprecated("Use 'area' instead")
   def square_area(self) -> float:
       return self.width * self.height
   ```

7. **Private Fields**: Private computed fields (starting with `_`) have `repr=False` by default.
   ```python
   @computed_field  # repr=False by default for _private fields
   @property
   def _internal_value(self) -> int:
       return 42
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
    children: list["CorrectNode"] = Field(default_factory=list)  # Works with string reference

# Remember to rebuild the model for forward references
CorrectNode.model_rebuild()
```

Using string literals for forward references allows you to reference a class within its own definition. Don't forget to call `model_rebuild()` after defining the model.

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

When overriding fields in subclasses, ensure the field type is compatible with the parent class's field.

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

`Optional[T]` only indicates that a field can be `None`, but it doesn't make the field optional during initialization. To make a field truly optional (not required), provide a default value.

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

### Immutable Models

Using immutable (frozen) models can help prevent bugs from unexpected state changes:

```python
import typing as t
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


# Make the entire model immutable
class Config(BaseModel, frozen=True):
    api_key: str
    timeout: int = 60
    created_at: datetime = Field(default_factory=datetime.now)

# Only make specific fields immutable
class User(BaseModel):
    id: int = Field(frozen=True)  # ID can't be changed
    username: str = Field(frozen=True)  # Username can't be changed
    display_name: str  # Can be modified
    last_login: datetime = Field(default_factory=datetime.now)  # Can be modified


# Create instances
config = Config(api_key="secret")
user = User(id=1, username="johndoe", display_name="John")

# Try to modify
try:
    config.timeout = 30  # Raises ValidationError, entire model is frozen
except Exception as e:
    print(f"Error: {e}")

try:
    user.id = 2  # Raises ValidationError, field is frozen
except Exception as e:
    print(f"Error: {e}")

# This works because the field isn't frozen
user.display_name = "John Doe" 
```

Benefits of immutable models:

1. **Thread safety**: Immutable objects are inherently thread-safe
2. **Predictable behavior**: No surprise state changes
3. **Better caching**: Safe to cache without worrying about modifications
4. **Simpler debugging**: State doesn't change unexpectedly

When to use frozen models:
- Configuration objects
- Value objects
- Models representing completed transactions
- Any model where state shouldn't change after creation

### Modern Pydantic Practices

These patterns represent evolving best practices in Pydantic v2 development:

```python
import typing as t
from datetime import datetime
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, ConfigDict, ValidationInfo, field_validator


# 1. Use ConfigDict instead of Config class
class User(BaseModel):
    model_config = ConfigDict(
        frozen=False,
        str_strip_whitespace=True,
        validate_assignment=True,
        extra='forbid'
    )
    # ...fields...


# 2. Use classmethod validators with ValidationInfo
class Order(BaseModel):
    items: list[str]
    
    @field_validator('items')
    @classmethod
    def validate_items(cls, v: list[str], info: ValidationInfo) -> list[str]:
        # ValidationInfo provides access to context like:
        # - info.context: the validation context
        # - info.config: model configuration
        # - info.data: all data being validated
        return v


# 3. Prefer Annotated pattern for field constraints
from typing import Annotated

# Define reusable constraints
UserId = Annotated[int, Field(gt=0)]
Username = Annotated[str, Field(min_length=3, max_length=50)]
Email = Annotated[str, Field(pattern=r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$')]

# Use them consistently across models
class CreateUser(BaseModel):
    username: Username
    email: Email
    
class UpdateUser(BaseModel):
    id: UserId
    username: Username
    email: Email


# 4. Separate models based on purpose
# API Input Model
class UserCreateInput(BaseModel):
    """Validates user input from API"""
    username: str
    email: str
    password: str
    
    model_config = ConfigDict(extra='forbid')  # Reject unknown fields

# Database Model
class UserDB(BaseModel):
    """Represents user in database"""
    id: UUID = Field(default_factory=uuid4)
    username: str
    email: str
    hashed_password: str
    created_at: datetime = Field(default_factory=datetime.now)
    
    @classmethod
    def from_input(cls, input_data: UserCreateInput, hashed_pw: str) -> 'UserDB':
        """Create DB model from input model"""
        return cls(
            username=input_data.username,
            email=input_data.email,
            hashed_password=hashed_pw
        )

# API Output Model
class UserResponse(BaseModel):
    """Returns user data to client"""
    id: UUID
    username: str
    email: str
    created_at: datetime
    
    @classmethod
    def from_db(cls, db_model: UserDB) -> 'UserResponse':
        """Create response model from DB model"""
        return cls(
            id=db_model.id,
            username=db_model.username,
            email=db_model.email,
            created_at=db_model.created_at
        )
```

Key modern patterns to follow:

1. **Model separation**: Use separate models for input validation, domain logic, and API responses
2. **Factory methods**: Add classmethod factory methods for common transformations
3. **Reusable type definitions**: Define and reuse complex types with `Annotated`
4. **Explicit configuration**: Use `ConfigDict` with clear settings
5. **Context-aware validation**: Use `ValidationInfo` to access field context
6. **Type adapter usage**: Prefer TypeAdapter for validating non-model types

### Performance Optimization

Pydantic v2 offers significant performance improvements over v1 due to its Rust-based core. Here are best practices for optimizing performance further:

#### Using TypeAdapter Efficiently

For maximum performance with collections or repeated validations, create TypeAdapter instances once and reuse them:

```python
import typing as t
from pydantic import TypeAdapter


# Create adapters at module level
INT_LIST_ADAPTER = TypeAdapter(list[int])
USER_DICT_ADAPTER = TypeAdapter(dict[str, t.Any])


def process_many_items(data_batches: list[list[str]]) -> list[list[int]]:
    """Process many batches of items"""
    results = []
    
    # Reuse the same adapter for each batch
    for batch in data_batches:
        # Convert strings to integers and validate
        validated_batch = INT_LIST_ADAPTER.validate_python(batch)
        results.append(validated_batch)
    
    return results


def parse_many_user_dicts(user_dicts: list[dict]) -> list[dict]:
    """Parse and validate user dictionaries"""
    return [USER_DICT_ADAPTER.validate_python(user_dict) for user_dict in user_dicts]
```

#### Choosing the Right Validation Mode

Pydantic offers different validation modes that trade off between performance and strictness:

```python
from pydantic import BaseModel, ConfigDict


# Strict mode - slower but safest
class StrictUser(BaseModel):
    model_config = ConfigDict(strict=True)
    id: int
    name: str


# Default mode - balanced
class DefaultUser(BaseModel):
    id: int
    name: str


# Lax mode - fastest but less type checking
class LaxUser(BaseModel):
    model_config = ConfigDict(coerce_numbers_to_str=True)
    id: int  # Will accept strings like "123" and convert
    name: str


# Performance comparison
strict_user = StrictUser(id=1, name="John")  # id must be int
default_user = DefaultUser(id="1", name="John")  # "1" converted to int
lax_user = LaxUser(id="1", name="John")  # "1" converted to int, more conversions allowed
```

#### Deferring Schema Building

For types with complex or circular references, defer schema building:

```python
import typing as t
from pydantic import TypeAdapter, ConfigDict


# Forward references
class Tree:
    value: int
    children: list["Tree"] = []


# Defer expensive schema building
tree_adapter = TypeAdapter("Tree", ConfigDict(defer_build=True))

# Build schema when needed
tree_adapter.rebuild()

# Now use the adapter
tree = tree_adapter.validate_python({"value": 1, "children": []})
```

#### Minimizing Model Validation

When working with trusted data or for performance reasons, consider skipping validation:

```python
import typing as t
from pydantic import BaseModel


class User(BaseModel):
    id: int
    name: str
    email: str


# Without validation (unsafe but fast)
user_dict = {"id": 1, "name": "John", "email": "john@example.com"}
user = User.model_construct(**user_dict)  # No validation

# With validation (safe but slower)
validated_user = User.model_validate(user_dict)
```

#### Optimizing JSON Operations

When working with JSON data, use the built-in JSON methods for best performance:

```python
import typing as t
import json
from pydantic import BaseModel, TypeAdapter


class LogEntry(BaseModel):
    timestamp: str
    level: str
    message: str


# Process JSON logs efficiently
log_adapter = TypeAdapter(list[LogEntry])

def process_log_file(file_path: str) -> list[LogEntry]:
    """Process a file of JSON log entries"""
    with open(file_path, 'r') as f:
        # Parse JSON first
        log_data = json.load(f)
        
    # Then validate with Pydantic
    return log_adapter.validate_python(log_data)


# Generate JSON efficiently
def serialize_logs(logs: list[LogEntry]) -> str:
    """Serialize logs to JSON"""
    # Use model_dump_json directly
    return f"[{','.join(log.model_dump_json() for log in logs)}]"
```

#### Benchmarking Performance

To identify bottlenecks in your Pydantic usage, use profiling tools:

```python
import cProfile
import typing as t
from pydantic import BaseModel


class Item(BaseModel):
    id: int
    name: str
    tags: list[str] = []


def create_many_items(count: int) -> list[Item]:
    """Create many items for benchmarking"""
    return [
        Item(id=i, name=f"Item {i}", tags=[f"tag{i}", "common"])
        for i in range(count)
    ]


# Profile item creation
cProfile.run('create_many_items(10000)')
```

#### Memory Usage Optimization

For applications handling large data volumes, consider these memory optimizations:

```python
import typing as t
from pydantic import BaseModel, Field


class LightweightModel(BaseModel):
    # Use __slots__ to reduce memory overhead
    model_config = {"extra": "ignore", "frozen": True}
    
    id: int
    # Use simple types where possible
    name: str = ""  # Empty string default uses less memory than None
    active: bool = True  # Boolean uses less memory than string flags
    
    # Avoid large collections with unbounded size
    # Use Field constraints to limit collection sizes
    tags: list[str] = Field(default_factory=list, max_length=10)
    
    # Avoid deeply nested structures where possible
    # Use flatter structures when handling large volumes


# Process items in chunks to reduce peak memory usage
def process_large_dataset(file_path: str, chunk_size: int = 1000):
    """Process a large dataset in chunks to reduce memory usage"""
    from itertools import islice
    
    with open(file_path, 'r') as f:
        # Create a generator to avoid loading everything at once
        def item_generator():
            for line in f:
                yield LightweightModel.model_validate_json(line)
        
        # Process in chunks
        items = item_generator()
        while chunk := list(islice(items, chunk_size)):
            process_chunk(chunk)
            # Each chunk is garbage collected after processing


def process_chunk(items: list[LightweightModel]):
    """Process a chunk of items"""
    for item in items:
        # Do something with each item
        pass
```

### Pydantic Core Access

For the most performance-critical applications, you can access Pydantic's Rust core directly:

```python
import typing as t
from pydantic import BaseModel
from pydantic_core import CoreSchema, core_schema


# Define a custom schema directly with pydantic_core
int_str_schema = core_schema.union_schema([
    core_schema.int_schema(),
    core_schema.str_schema()
])

# Use in a model
class OptimizedModel(BaseModel):
    # Use a pre-defined core schema for a field
    value: t.Any = None
    
    # Override the core schema for this field
    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: t.Any, handler: t.Any
    ) -> CoreSchema:
        schema = handler(source_type)
        # Modify the schema for the 'value' field
        for field in schema['schema']['schema']['fields']:
            if field['name'] == 'value':
                field['schema'] = int_str_schema
        return schema
```

#### Core Performance Tips

1. **Reuse TypeAdapters**: Create once, use many times
2. **Batch validation**: Validate collections at once rather than items individually
3. **Choose the right validation mode**: Strict for safety, lax for performance
4. **Use model_construct**: Skip validation for trusted data
5. **Profile and benchmark**: Identify bottlenecks specific to your application
6. **Consider memory usage**: Especially important for large datasets
7. **Use Pydantic core directly**: For extreme performance requirements

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

Pydantic has a rich ecosystem of plugins and extensions:

- **[pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)**: Settings management with environment variables support
- **[pydantic-extra-types](https://github.com/pydantic/pydantic-extra-types)**: Additional types like phone numbers, payment cards, etc.
- **[pydantic-factories](https://github.com/starlite-api/pydantic-factories)**: Testing utilities for generating fake data
- **[pydantic-mongo](https://github.com/mongomock/mongomock)**: MongoDB ODM based on Pydantic models
- **[pydantic-yaml](https://github.com/NowanIlfideme/pydantic-yaml)**: YAML support for Pydantic models
- **[fastui](https://github.com/pydantic/fastui)**: Build reactive web UIs with Python and Pydantic models
- **[sqlmodel](https://github.com/tiangolo/sqlmodel)**: SQL databases with Pydantic and SQLAlchemy
- **[beanie](https://github.com/roman-right/beanie)**: MongoDB ODM built on Pydantic
- **[litestar](https://github.com/litestar-org/litestar)**: High-performance ASGI framework with native Pydantic support
- **[strawberry](https://github.com/strawberry-graphql/strawberry)**: GraphQL with Pydantic support
- **[edgy](https://github.com/tarsil/edgy)**: Asynchronous ORM with Pydantic

#### Development and Testing

- **[logfire](https://pydantic.dev/logfire)**: Application monitoring with Pydantic support
- **[pydantic-marshals](https://github.com/rajivsarvepalli/pydantic-marshals)**: Input/output marshalling for integrations
- **[dirty-equals](https://github.com/samuelcolvin/dirty-equals)**: Pytest assertions with smart equality
- **[faker-pydantic](https://github.com/arthurio/faker-pydantic)**: Fake data generation with Pydantic models

#### Example Integration with Logfire Monitoring

```python
# Monitoring Pydantic validation with Logfire
import logfire
from datetime import datetime
from pydantic import BaseModel

# Configure Logfire and instrument Pydantic
logfire.configure()
logfire.instrument_pydantic()

class Delivery(BaseModel):
    timestamp: datetime
    dimensions: tuple[int, int]

# This will record validation details to Logfire
try:
    delivery = Delivery(
        timestamp='2023-01-02T03:04:05Z', 
        dimensions=['10', 'invalid']  # This will cause validation to fail
    )
except Exception as e:
    print(f"Validation error: {e}")
    # Error details automatically sent to Logfire
```

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

#### Testing FastAPI and Pydantic Applications

For testing FastAPI applications with Pydantic models, you can use pytest fixtures:

```python
import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel, EmailStr
from typing import Generator, List
from uuid import UUID, uuid4
from fastapi import FastAPI, Depends, HTTPException

# Model definitions
class UserBase(BaseModel):
    email: EmailStr
    username: str
    
class UserCreate(UserBase):
    password: str
    
class UserResponse(UserBase):
    id: UUID
    is_active: bool
    
# Mock database
users_db = {}

# App and dependencies
app = FastAPI()

def get_user_by_id(user_id: UUID):
    if user_id not in users_db:
        raise HTTPException(status_code=404, detail="User not found")
    return users_db[user_id]

@app.post("/users/", response_model=UserResponse)
def create_user(user: UserCreate):
    user_id = uuid4()
    users_db[user_id] = {**user.model_dump(), "id": user_id, "is_active": True}
    return users_db[user_id]

@app.get("/users/{user_id}", response_model=UserResponse)
def read_user(user = Depends(get_user_by_id)):
    return user

# Test fixtures
@pytest.fixture
def client() -> Generator:
    with TestClient(app) as c:
        yield c

@pytest.fixture
def sample_user() -> UserCreate:
    return UserCreate(
        email="test@example.com",
        username="testuser",
        password="password123"
    )

@pytest.fixture
def created_user(client, sample_user) -> UserResponse:
    response = client.post("/users/", json=sample_user.model_dump())
    return UserResponse(**response.json())

# Tests
def test_create_user(client, sample_user):
    response = client.post("/users/", json=sample_user.model_dump())
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == sample_user.email
    assert data["username"] == sample_user.username
    assert "id" in data
    assert "password" not in data

def test_get_user(client, created_user):
    response = client.get(f"/users/{created_user.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(created_user.id)
    assert data["email"] == created_user.email
```

This testing approach:
1. Uses pytest fixtures to set up test data and clients
2. Leverages Pydantic models for both request/response validation and test data creation
3. Uses model_dump() to convert models to dictionaries for API requests
4. Maintains type safety throughout the test code

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
    """Model for creating new users"""
    password: str = Field(min_length=8)
    password_confirm: str = Field(min_length=8)
    
    @field_validator('password')
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain an uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain a lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain a digit')
        return v
    
    @model_validator(mode='after')
    def passwords_match(self) -> 'UserCreate':
        if self.password != self.password_confirm:
            raise ValueError('Passwords do not match')
        return self


# Output models (for API responses)
class UserRead(UserBase):
    """Model for user responses"""
    id: UUID
    created_at: datetime
    is_active: bool


# Update models (for partial updates)
class UserUpdate(BaseModel):
    """Model for updating existing users"""
    email: t.Optional[EmailStr] = None
    username: t.Optional[str] = Field(None, min_length=3, max_length=50)
    is_active: t.Optional[bool] = None


# Database models (internal representation)
class UserDB(UserBase):
    """Internal database model for users"""
    id: UUID = Field(default_factory=uuid4)
    hashed_password: str
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: t.Optional[datetime] = None
    is_active: bool = True


# Usage in a REST API context
def register_user(user_data: UserCreate) -> UserRead:
    """Register a new user"""
    # Validate input with UserCreate model
    user = UserCreate(**user_data)
    
    # Convert to database model
    user_db = UserDB(
        email=user.email,
        username=user.username,
        hashed_password=f"hashed_{user.password}"  # Replace with actual hashing
    )
    
    # Save to database (simulated)
    print(f"Saving user to database: {user_db.model_dump(exclude={'hashed_password'})}")
    
    # Return read model for API response
    return UserRead(
        id=user_db.id,
        email=user_db.email,
        username=user_db.username,
        created_at=user_db.created_at,
        is_active=user_db.is_active
    )


# API endpoint example
def update_user(user_id: UUID, user_data: UserUpdate) -> UserRead:
    """Update an existing user"""
    # Get existing user from database (simulated)
    existing_user = UserDB(
        id=user_id,
        email="existing@example.com",
        username="existing_user",
        hashed_password="hashed_password",
        created_at=datetime(2023, 1, 1)
    )
    
    # Update only fields that are set in the update model
    update_data = user_data.model_dump(exclude_unset=True)
    
    # Apply updates to existing user
    for field, value in update_data.items():
        setattr(existing_user, field, value)
    
    # Update the updated_at timestamp
    existing_user.updated_at = datetime.now()
    
    # Save to database (simulated)
    print(f"Updating user in database: {existing_user.model_dump(exclude={'hashed_password'})}")
    
    # Return read model for API response
    return UserRead(
        id=existing_user.id,
        email=existing_user.email,
        username=existing_user.username,
        created_at=existing_user.created_at,
        is_active=existing_user.is_active
    )
```

### Pagination and Collection Responses

Use generic models for consistent API responses:

```python
import typing as t
from pydantic import BaseModel, Field


T = t.TypeVar('T')


class Page(t.Generic[T]):
    """Generic paginated response"""
    items: list[T]
    total: int
    page: int
    size: int
    
    @property
    def pages(self) -> int:
        """Calculate total number of pages"""
        return (self.total + self.size - 1) // self.size


class PaginationParams(BaseModel):
    """Common pagination parameters"""
    page: int = Field(default=1, gt=0)
    size: int = Field(default=50, gt=0, le=100)


class ResponseList(t.Generic[T], BaseModel):
    """Generic list response model"""
    data: list[T]
    count: int
    
    
class ResponsePage(t.Generic[T], BaseModel):
    """Generic paginated response model"""
    data: list[T]
    pagination: Page
    
    
# Example usage with user model
def list_users(params: PaginationParams) -> ResponsePage[UserRead]:
    """List users with pagination"""
    # Fetch from database (simulated)
    users = [
        UserRead(
            id=uuid4(),
            email=f"user{i}@example.com",
            username=f"user{i}",
            created_at=datetime.now(),
            is_active=True
        )
        for i in range(1, 101)
    ]
    
    # Apply pagination
    start = (params.page - 1) * params.size
    end = start + params.size
    page_users = users[start:end]
    
    # Create pagination info
    pagination = Page(
        items=page_users,
        total=len(users),
        page=params.page,
        size=params.size
    )
    
    # Return paginated response
    return ResponsePage(
        data=page_users,
        pagination=pagination
    )
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

#### Benefits of the Pipeline API

The Pipeline API offers several advantages over traditional validators:

1. **Type Safety**: Each step in the pipeline maintains proper type information, helping catch potential issues at development time.

2. **Composability**: Easily chain multiple validation and transformation steps in a logical sequence.

3. **Readability**: The pipeline clearly shows the sequence and purpose of each validation/transformation step.

4. **Reusability**: Pipeline components can be easily reused across different models and fields.

5. **Dependencies**: Computed values can explicitly declare their dependencies on other fields.

Available pipeline components include:

- **`pipeline.validate(type)`**: Validates against a specific type
- **`pipeline.transform(func)`**: Applies a transformation function
- **`pipeline.predicate(func, error_message)`**: Tests a condition and raises an error if it fails
- **`pipeline.constraint(func, error_message)`**: Applies a constraint with custom error message
- **`pipeline.computed(func, dependencies)`**: Computes a value based on other fields (specified in dependencies)

While this API is still experimental, it represents a more elegant approach to complex validation scenarios and may become the preferred way to handle sophisticated validation in future versions.

### Working With TypedDict

TypeAdapter makes it easy to use Python's `TypedDict` with Pydantic validation:

```python
import typing as t
from typing_extensions import NotRequired, Required, TypedDict
from pydantic import TypeAdapter, ValidationError

# Define a TypedDict
class UserDict(TypedDict):
    id: int
    name: str
    email: NotRequired[str]  # Optional field in Python 3.11+

# Create a TypeAdapter for the TypedDict
user_adapter = TypeAdapter(UserDict)

# Validate data against the TypedDict
try:
    # Validation works with type coercion
    user = user_adapter.validate_python({"id": "123", "name": "John"})
    print(user)  # {'id': 123, 'name': 'John'}
    
    # Validation errors are raised for invalid data
    user_adapter.validate_python({"name": "John"})  # Missing required 'id'
except ValidationError as e:
    print(e)
    # 1 validation error for typed dict
    # id
    #   Field required [type=missing, input_value={'name': 'John'}, input_type=dict]

# Generate JSON schema
schema = user_adapter.json_schema()
print(schema)
# {
#   "properties": {
#     "id": {"title": "Id", "type": "integer"},
#     "name": {"title": "Name", "type": "string"},
#     "email": {"title": "Email", "type": "string"}
#   },
#   "required": ["id", "name"],
#   "title": "UserDict",
#   "type": "object"
# }
```

#### TypedDict Advanced Features

Pydantic supports many TypedDict features introduced in newer Python versions:

```python
from typing_extensions import NotRequired, Required, TypedDict
from pydantic import TypeAdapter

# Total=False makes all fields optional by default
class ConfigDict(TypedDict, total=False):
    debug: bool
    log_level: str
    
    # Required marks specific fields as required
    api_key: Required[str]

# Inheritance works as expected
class UserConfig(ConfigDict):
    username: str  # Inherited fields remain with their original required status
    
# With NotRequired (Python 3.11+) you can mark specific fields as optional
class Product(TypedDict):
    id: int
    name: str
    description: NotRequired[str]  # Optional field

# Create adapters
config_adapter = TypeAdapter(ConfigDict)
user_config_adapter = TypeAdapter(UserConfig)
product_adapter = TypeAdapter(Product)

# Validate
config = config_adapter.validate_python({"api_key": "secret"})  # debug and log_level are optional
user_config = user_config_adapter.validate_python({"api_key": "secret", "username": "john"})
product = product_adapter.validate_python({"id": 1, "name": "Laptop"})  # description is optional
```
#### Limitations of TypedDict

There are some limitations to be aware of when using TypedDict with Pydantic:

1. **Computed fields** are not yet supported with TypedDict (as of Pydantic v2.8)
2. When validating nested TypedDict structures, all validation happens at once rather than step by step
3. Some advanced field customization features may not work with TypedDict fields

#### Protocol Validation with Custom Validators

Pydantic v2 allows powerful protocol validation with custom validators:

```python
import typing as t
from datetime import datetime
from typing_extensions import Protocol, runtime_checkable
from pydantic import TypeAdapter, ValidationError, GetCoreSchemaHandler, BeforeValidator
from pydantic_core import core_schema


# Define a protocol
@runtime_checkable
class HasTimestamp(Protocol):
    """Protocol for objects with timestamp access"""
    def get_timestamp(self) -> datetime: ...
    

# Define classes that implement the protocol
class Event:
    def __init__(self, event_time: datetime):
        self._time = event_time
        
    def get_timestamp(self) -> datetime:
        return self._time


class LogEntry:
    def __init__(self, log_time: datetime, level: str, message: str):
        self.log_time = log_time
        self.level = level
        self.message = message
        
    def get_timestamp(self) -> datetime:
        return self.log_time


# Custom validator for protocol checking
def validate_has_timestamp(v: t.Any) -> HasTimestamp:
    if isinstance(v, HasTimestamp):
        return v
    raise ValueError(f"Expected object with get_timestamp method, got {type(v)}")


# Create a type adapter with the protocol
timestamp_adapter = TypeAdapter(
    t.Annotated[HasTimestamp, BeforeValidator(validate_has_timestamp)]
)

# Use the adapter to validate objects
event = Event(datetime.now())
log_entry = LogEntry(datetime.now(), "INFO", "System started")

# Both objects implement the protocol and pass validation
valid_event = timestamp_adapter.validate_python(event)
valid_log = timestamp_adapter.validate_python(log_entry)

# This will fail - does not implement the protocol
try:
    timestamp_adapter.validate_python({"timestamp": "2023-01-01T12:00:00"})
except ValidationError as e:
    print(f"Validation error: {e}")


# Advanced: Creating a protocol validator directly with core schema
class HasIDAndName(Protocol):
    id: int
    name: str

def create_protocol_validator_schema(
    _core_schema: core_schema.CoreSchema, handler: GetCoreSchemaHandler
) -> core_schema.CoreSchema:
    return core_schema.general_after_validator_function(
        lambda v: v if hasattr(v, 'id') and hasattr(v, 'name') else None,
        handler(t.Any),
        error_message="Object must have 'id' and 'name' attributes",
    )

# Use in a model
from pydantic import create_model

ProtocolModel = create_model(
    'ProtocolModel',
    item=(
        t.Annotated[HasIDAndName, create_protocol_validator_schema],
        ...  # Required field
    )
)
```

#### Benefits of Protocol Validation

1. **Structural typing**: Validate based on what objects can do, not what they are
2. **Loose coupling**: No inheritance requirements between validated classes
3. **Framework-agnostic**: Works with any objects that match the protocol
4. **Runtime verification**: Uses Python's runtime protocol checking

When to use protocols:
- Integration between different libraries or systems
- Plugin architectures
- Testing with mock objects
- Domain modeling with behavior focus

### Data Processing Pipeline

Use Pydantic in data processing pipelines for validation and transformation:

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
    """Raw sensor data with potentially unparsed values"""
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


# Processed data model with type conversion and validation
class ProcessedDataPoint(BaseModel):
    """Cleaned and validated sensor data with proper types"""
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


# Pipeline result model
class ProcessingResult(BaseModel):
    """Results of a data processing batch operation"""
    processed: int = 0
    errors: int = 0
    error_details: list[dict] = Field(default_factory=list)
    processing_time: float = 0.0
    processed_data: list[ProcessedDataPoint] = Field(default_factory=list)


# ETL Processing pipeline
class DataProcessor:
    def __init__(self):
        # Create adapter once for performance
        self.raw_adapter = TypeAdapter(list[RawDataPoint])
        
    def process_batch(self, raw_data: list[dict]) -> ProcessingResult:
        """Process a batch of raw data points."""
        start_time = datetime.now()
        result = ProcessingResult()
        
        try:
            # Validate all raw data points at once
            validated_raw = self.raw_adapter.validate_python(raw_data)
            
            # Process each point
            for raw_point in validated_raw:
                try:
                    processed = ProcessedDataPoint.from_raw(raw_point)
                    result.processed_data.append(processed)
                    result.processed += 1
                except ValidationError as e:
                    result.errors += 1
                    result.error_details.append({
                        "raw_data": raw_point.model_dump(),
                        "error": e.errors()
                    })
                    
        except ValidationError as e:
            result.errors = len(raw_data)
            result.error_details.append({"error": "Batch validation failed", "details": e.errors()})
            
        result.processing_time = (datetime.now() - start_time).total_seconds()
        return result


# Usage example
def process_sensor_data(data_batch: list[dict]) -> dict:
    """Process a batch of sensor data."""
    processor = DataProcessor()
    result = processor.process_batch(data_batch)
    
    # Create a summary report
    return {
        "summary": {
            "total": result.processed + result.errors,
            "processed": result.processed,
            "errors": result.errors,
            "processing_time_ms": result.processing_time * 1000
        },
        "data": [point.model_dump() for point in result.processed_data],
        "errors": result.error_details
    }


# Example usage with sample data
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

# Results of processing
# result = process_sensor_data(sample_data)
# print(f"Processed {result['summary']['processed']} records with {result['summary']['errors']} errors")
```

### Configuration and Settings Management

Pydantic is ideal for managing application settings:

```python
import typing as t
import os
from pydantic import BaseModel, Field, field_validator, SecretStr
from functools import lru_cache


class DatabaseSettings(BaseModel):
    """Database connection settings"""
    url: str
    port: int = 5432
    username: str
    password: SecretStr
    database: str
    
    @property
    def connection_string(self) -> str:
        """Build PostgreSQL connection string"""
        return f"postgresql://{self.username}:{self.password.get_secret_value()}@{self.url}:{self.port}/{self.database}"


class LoggingSettings(BaseModel):
    """Logging configuration"""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file: t.Optional[str] = None
    
    @field_validator('level')
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Ensure log level is valid"""
        allowed = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in allowed:
            raise ValueError(f"Log level must be one of {', '.join(allowed)}")
        return v.upper()


class AppSettings(BaseModel):
    """Application settings"""
    app_name: str = "My Application"
    version: str = "0.1.0"
    debug: bool = False
    env: str = Field(default="development")
    allowed_origins: list[str] = ["http://localhost:3000"]
    db: DatabaseSettings
    logging: LoggingSettings = Field(default_factory=lambda: LoggingSettings())
    
    @field_validator('env')
    @classmethod
    def validate_env(cls, v: str) -> str:
        """Validate environment name"""
        allowed_envs = ['development', 'testing', 'production']
        if v not in allowed_envs:
            raise ValueError(f"Environment must be one of: {', '.join(allowed_envs)}")
        return v
    
    @classmethod
    def from_env(cls) -> 'AppSettings':
        """Load settings from environment variables with proper prefixing"""
        return cls(
            app_name=os.getenv("APP_NAME", "My Application"),
            version=os.getenv("APP_VERSION", "0.1.0"),
            debug=os.getenv("APP_DEBUG", "false").lower() in ("true", "1", "yes"),
            env=os.getenv("APP_ENV", "development"),
            allowed_origins=os.getenv("APP_ALLOWED_ORIGINS", "http://localhost:3000").split(","),
            db=DatabaseSettings(
                url=os.getenv("DB_URL", "localhost"),
                port=int(os.getenv("DB_PORT", "5432")),
                username=os.getenv("DB_USERNAME", "postgres"),
                password=SecretStr(os.getenv("DB_PASSWORD", "")),
                database=os.getenv("DB_DATABASE", "app"),
            ),
            logging=LoggingSettings(
                level=os.getenv("LOG_LEVEL", "INFO"),
                format=os.getenv("LOG_FORMAT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"),
                file=os.getenv("LOG_FILE"),
            )
        )


# Use lru_cache to avoid loading settings multiple times
@lru_cache()
def get_settings() -> AppSettings:
    """Load settings from environment with caching."""
    try:
        return AppSettings.from_env()
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

### Pydantic with SQLAlchemy

Pydantic can be used alongside SQLAlchemy to create a clean separation between database models and API schemas:

```python
import typing as t
from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import Column, String, Boolean, DateTime, Integer, ForeignKey, create_engine
from sqlalchemy.dialects.postgresql import UUID as SQLUUID
from sqlalchemy.orm import declarative_base, relationship, Session
from pydantic import BaseModel, Field, ConfigDict


# SQLAlchemy Models
Base = declarative_base()


class UserDB(Base):
    """SQLAlchemy User model"""
    __tablename__ = "users"
    
    id = Column(SQLUUID, primary_key=True, default=uuid4)
    email = Column(String, unique=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, nullable=True)
    
    # Relationships
    posts = relationship("PostDB", back_populates="author")
    

class PostDB(Base):
    """SQLAlchemy Post model"""
    __tablename__ = "posts"
    
    id = Column(SQLUUID, primary_key=True, default=uuid4)
    title = Column(String, index=True)
    content = Column(String)
    published = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    author_id = Column(SQLUUID, ForeignKey("users.id"))
    
    # Relationships
    author = relationship("UserDB", back_populates="posts")


# Pydantic Models for API
class UserBase(BaseModel):
    """Base Pydantic model for User"""
    email: str
    username: str
    is_active: bool = True


class UserCreate(UserBase):
    """User creation model"""
    password: str


class UserRead(UserBase):
    """User response model"""
    id: UUID
    created_at: datetime
    
    # Configure ORM integration
    model_config = ConfigDict(
        from_attributes=True  # Allow creating model from SQLAlchemy model
    )


class PostBase(BaseModel):
    """Base Pydantic model for Post"""
    title: str
    content: str
    published: bool = False


class PostCreate(PostBase):
    """Post creation model"""
    pass


class PostRead(PostBase):
    """Post response model"""
    id: UUID
    created_at: datetime
    author_id: UUID
    
    # Optional nested author model
    author: t.Optional[UserRead] = None
    
    # Configure ORM integration
    model_config = ConfigDict(
        from_attributes=True
    )


# Database CRUD operations
class UserRepository:
    def __init__(self, session: Session):
        self.session = session
    
    def create(self, user_data: UserCreate) -> UserDB:
        """Create a new user"""
        # Hash password in a real application
        hashed_password = f"hashed_{user_data.password}"
        
        # Convert Pydantic model to SQLAlchemy model
        db_user = UserDB(
            email=user_data.email,
            username=user_data.username,
            hashed_password=hashed_password,
            is_active=user_data.is_active
        )
        
        # Add to database
        self.session.add(db_user)
        self.session.commit()
        self.session.refresh(db_user)
        
        return db_user
    
    def get_by_id(self, user_id: UUID) -> t.Optional[UserDB]:
        """Get user by ID"""
        return self.session.query(UserDB).filter(UserDB.id == user_id).first()
    
    def get_with_posts(self, user_id: UUID) -> t.Optional[UserDB]:
        """Get user with related posts"""
        return (
            self.session.query(UserDB)
            .filter(UserDB.id == user_id)
            .options(relationship("posts"))
            .first()
        )


# API endpoints (example usage)
def create_user_endpoint(user_data: UserCreate, session: Session) -> UserRead:
    """API endpoint to create user"""
    # Use repository pattern
    repo = UserRepository(session)
    db_user = repo.create(user_data)
    
    # Convert SQLAlchemy model to Pydantic model
    return UserRead.model_validate(db_user)


def get_user_with_posts(user_id: UUID, session: Session) -> dict:
    """API endpoint to get user with posts"""
    repo = UserRepository(session)
    db_user = repo.get_with_posts(user_id)
    
    if not db_user:
        raise ValueError("User not found")
    
    # Convert user and nested posts
    user = UserRead.model_validate(db_user)
    posts = [PostRead.model_validate(post) for post in db_user.posts]
    
    # Return combined response
    return {
        "user": user.model_dump(),
        "posts": [post.model_dump() for post in posts]
    }
```

#### Best Practices with Pydantic and ORMs

When using Pydantic with ORMs like SQLAlchemy, Django ORM, or others:

1. **Separation of concerns**: Keep database models separate from API models
   - Database models: Focus on storage, relationships, and database constraints
   - API models: Focus on validation, serialization, and documentation

2. **Use `from_attributes=True`** in model_config to enable creating Pydantic models from ORM models:
   ```python
   model_config = ConfigDict(from_attributes=True)
   ```

3. **Convert at boundaries**: Convert between ORM and Pydantic models at application boundaries
   - Incoming data → Pydantic validation → ORM model → Database
   - Database → ORM model → Pydantic model → API response

4. **Avoid circular imports**:
   - Place ORM models in separate modules from Pydantic models
   - Use forward references for circular relationships: `author: "UserRead" = None`

5. **Handle relationships carefully**:
   - Use lazily-loaded relationships in ORM models
   - Use explicit joins when needed for performance
   - Consider depth limitations for nested serialization

### FastAPI Integration

FastAPI is built around Pydantic models for request validation and documentation:

```python
import typing as t
from datetime import datetime
from uuid import UUID, uuid4
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, Field, EmailStr


# Pydantic models
class UserCreate(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8)


class UserRead(BaseModel):
    id: UUID
    email: EmailStr
    username: str
    created_at: datetime
    is_active: bool


class Token(BaseModel):
    access_token: str
    token_type: str


# FastAPI app
app = FastAPI(title="Pydantic API Example")

# Auth utilities (simplified)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


async def get_current_user(token: str = Depends(oauth2_scheme)) -> UserRead:
    """Get current user from token"""
    # This would validate the token and get the user in a real app
    # For this example, just return a mock user
    return UserRead(
        id=uuid4(),
        email="user@example.com",
        username="current_user",
        created_at=datetime.now(),
        is_active=True
    )


# API endpoints
@app.post("/users/", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(user_data: UserCreate) -> UserRead:
    """Create a new user"""
    # In a real app, we would save to database
    # For example purposes, just create a mock response
    return UserRead(
        id=uuid4(),
        email=user_data.email,
        username=user_data.username,
        created_at=datetime.now(),
        is_active=True
    )


@app.get("/users/me/", response_model=UserRead)
async def read_users_me(current_user: UserRead = Depends(get_current_user)) -> UserRead:
    """Get current user information"""
    return current_user


@app.get("/users/{user_id}", response_model=UserRead)
async def read_user(user_id: UUID) -> UserRead:
    """Get user by ID"""
    # In a real app, we would query the database
    # Simulate user not found for a specific ID
    if user_id == UUID("00000000-0000-0000-0000-000000000000"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return UserRead(
        id=user_id,
        email=f"user-{user_id}@example.com",
        username=f"user-{str(user_id)[:8]}",
        created_at=datetime.now(),
        is_active=True
    )
```

#### Key Benefits of Pydantic in FastAPI

1. **Automatic request validation**: FastAPI automatically validates request bodies, query parameters, path parameters, etc., using Pydantic models

2. **Automatic documentation**: Pydantic models are used to generate OpenAPI schema and Swagger UI documentation

3. **Type safety**: Type annotations in Pydantic models provide type hints for better IDE support and catch errors at development time

4. **Response serialization**: `response_model` parameter uses Pydantic to serialize responses according to the model definition

5. **Integration with dependency injection**: Pydantic models can be used as dependencies to validate and transform input data

### Testing with Pydantic

Pydantic models can be very useful in testing to create fixtures, validate test data, and simplify test assertions:

```python
import typing as t
import json
import pytest
from datetime import datetime, timedelta
from pydantic import BaseModel, TypeAdapter, ValidationError, Field


# Models to test
class User(BaseModel):
    id: int
    name: str
    email: str
    role: str = "user"
    created_at: datetime


class UserService:
    """Example service class to test"""
    def get_user(self, user_id: int) -> User:
        """Get user from database (mocked)"""
        # This would normally fetch from a database
        if user_id == 404:
            return None
        return User(
            id=user_id,
            name=f"User {user_id}",
            email=f"user{user_id}@example.com",
            role="admin" if user_id == 1 else "user",
            created_at=datetime.now() - timedelta(days=user_id)
        )
    
    def create_user(self, user_data: dict) -> User:
        """Create a new user (mocked)"""
        # Validate user data
        user = User(**user_data, created_at=datetime.now())
        # Would normally save to database
        return user


# Test fixtures using pydantic
@pytest.fixture
def admin_user() -> User:
    """Create an admin user fixture"""
    return User(
        id=1,
        name="Admin User",
        email="admin@example.com",
        role="admin",
        created_at=datetime.now()
    )


@pytest.fixture
def regular_user() -> User:
    """Create a regular user fixture"""
    return User(
        id=2,
        name="Regular User",
        email="user@example.com",
        role="user",
        created_at=datetime.now()
    )


@pytest.fixture
def user_service() -> UserService:
    """Create a user service for testing"""
    return UserService()


# Unit tests
def test_get_user(user_service: UserService):
    """Test getting a user by ID"""
    user = user_service.get_user(1)
    
    # Use model_dump to get dict for assertions
    user_dict = user.model_dump()
    assert user_dict["id"] == 1
    assert user_dict["role"] == "admin"
    assert isinstance(user_dict["created_at"], datetime)


def test_create_user(user_service: UserService):
    """Test creating a user"""
    new_user_data = {
        "id": 3,
        "name": "New User",
        "email": "new@example.com"
    }
    
    user = user_service.create_user(new_user_data)
    assert user.id == 3
    assert user.name == "New User"
    assert user.role == "user"  # Default value
    
    # Test with invalid data
    invalid_data = {
        "id": "not-an-int",  # Type error
        "name": "Invalid User",
        "email": "invalid-email"  # Invalid email format
    }
    
    with pytest.raises(ValidationError):
        user_service.create_user(invalid_data)


# Test with parametrize
@pytest.mark.parametrize("user_id,expected_role", [
    (1, "admin"),  # Admin user
    (2, "user"),   # Regular user
    (3, "user"),   # Another regular user
])
def test_user_roles(user_service: UserService, user_id: int, expected_role: str):
    """Test different user roles"""
    user = user_service.get_user(user_id)
    assert user.role == expected_role


# Test with TypeAdapter for bulk validation
def test_bulk_user_validation():
    """Test validating multiple users at once"""
    # Define test data
    users_data = [
        {"id": 1, "name": "User 1", "email": "user1@example.com", "created_at": "2023-01-01T00:00:00"},
        {"id": 2, "name": "User 2", "email": "user2@example.com", "created_at": "2023-01-02T00:00:00"},
        {"id": 3, "name": "User 3", "email": "user3@example.com", "created_at": "2023-01-03T00:00:00"},
    ]
    
    # Create a TypeAdapter for List[User]
    user_list_adapter = TypeAdapter(list[User])
    
    # Validate all users at once
    validated_users = user_list_adapter.validate_python(users_data)
    
    # Assertions
    assert len(validated_users) == 3
    assert all(isinstance(user, User) for user in validated_users)
    assert validated_users[0].id == 1
    assert validated_users[1].name == "User 2"
    assert validated_users[2].email == "user3@example.com"


# Integration test with JSON responses
def test_api_response(client):
    """Test API response validation (with a mock client)"""
    # This would normally be an HTTP client
    class MockClient:
        def get(self, url: str) -> dict:
            if url == "/users/1":
                return {
                    "id": 1,
                    "name": "API User",
                    "email": "api@example.com",
                    "role": "user",
                    "created_at": "2023-01-01T00:00:00"
                }
            return {"error": "Not found"}
    
    client = MockClient()
    
    # Get response from API
    response = client.get("/users/1")
    
    # Validate response against Pydantic model
    user = User.model_validate(response)
    
    # Assert using model
    assert user.id == 1
    assert user.name == "API User"
    assert user.created_at.year == 2023
```

#### Pydantic for API Testing

When testing APIs that use Pydantic models, you can leverage the same models for validation:

```python
import typing as t
import pytest
import requests
from pydantic import BaseModel, TypeAdapter, ValidationError


# API Models
class UserResponse(BaseModel):
    id: int
    name: str
    email: str


class ErrorResponse(BaseModel):
    detail: str
    status_code: int


# Response validator
class ResponseValidator:
    @staticmethod
    def validate_user_response(response_json: dict) -> UserResponse:
        """Validate a user response against the expected schema"""
        return UserResponse.model_validate(response_json)
    
    @staticmethod
    def validate_user_list_response(response_json: list) -> list[UserResponse]:
        """Validate a list of users against the expected schema"""
        user_list_adapter = TypeAdapter(list[UserResponse])
        return user_list_adapter.validate_python(response_json)
    
    @staticmethod
    def validate_error_response(response_json: dict) -> ErrorResponse:
        """Validate an error response against the expected schema"""
        return ErrorResponse.model_validate(response_json)


# API tests
class TestUserAPI:
    BASE_URL = "https://api.example.com"
    
    def test_get_user(self):
        """Test getting a user by ID"""
        # This would normally make a real API call
        # Mocked for example purposes
        response_json = {
            "id": 1,
            "name": "John Doe",
            "email": "john@example.com"
        }
        
        # Validate response structure
        user = ResponseValidator.validate_user_response(response_json)
        
        # Assert using model
        assert user.id == 1
        assert user.name == "John Doe"
        assert user.email == "john@example.com"
    
    def test_get_users(self):
        """Test getting a list of users"""
        # Mocked response
        response_json = [
            {"id": 1, "name": "User 1", "email": "user1@example.com"},
            {"id": 2, "name": "User 2", "email": "user2@example.com"},
        ]
        
        # Validate response structure
        users = ResponseValidator.validate_user_list_response(response_json)
        
        # Assert using models
        assert len(users) == 2
        assert users[0].id == 1
        assert users[1].name == "User 2"
    
    def test_error_response(self):
        """Test error response validation"""
        # Mocked error response
        response_json = {
            "detail": "User not found",
            "status_code": 404
        }
        
        # Validate error response
        error = ResponseValidator.validate_error_response(response_json)
        
        # Assert using model
        assert error.detail == "User not found"
        assert error.status_code == 404
```

#### Testing Best Practices with Pydantic

1. **Create fixtures based on Pydantic models**: Use models to define test fixtures for consistent test data

2. **Validate test input and output**: Use models to validate both test inputs and expected outputs

3. **Simplify complex assertions**: Compare model instances instead of deep dictionary comparisons

4. **Test validation logic**: Test model validation rules explicitly, especially for domain-specific validators

5. **Use `TypeAdapter` for collections**: When testing with collections of objects, use TypeAdapter for efficient validation

6. **Mock external services with validated data**: When mocking external services, ensure the mock data conforms to your models