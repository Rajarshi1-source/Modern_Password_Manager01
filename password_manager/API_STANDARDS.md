# API Standards

## Standardized API Responses

All API responses in the Password Manager project follow a standardized format to ensure consistency across endpoints.

### Success Response Format

```json
{
  "success": true,
  "message": "Operation successful",
  // Additional data specific to the endpoint
}
```

### Error Response Format

```json
{
  "success": false,
  "message": "Error message",
  "code": "error_code",
  "details": { /* Additional error details */ }
}
```

## How to Use Standardized Responses

### In API Views

To ensure consistent API responses, use the `success_response` and `error_response` utility functions in your views:

```python
from password_manager.api_utils import error_response, success_response

# Success response example
@api_view(['GET'])
def my_api_view(request):
    data = {"items": [...]}
    return success_response(
        data=data,
        message="Items retrieved successfully",
        status_code=status.HTTP_200_OK
    )

# Error response example
@api_view(['POST'])
def create_item(request):
    if not request.data:
        return error_response(
            message="No data provided",
            code="missing_data",
            status_code=status.HTTP_400_BAD_REQUEST,
            details={"required_fields": ["name", "value"]}
        )
```

### Response Structure

#### Success Response Parameters

| Parameter  | Description                                   | Required | Default Value      |
|------------|-----------------------------------------------|----------|-------------------|
| data       | The main payload to return to the client      | No       | None              |
| message    | Human-readable success message                | No       | "Operation successful" |
| status_code| HTTP status code                              | No       | 200 (OK)          |

#### Error Response Parameters

| Parameter  | Description                                   | Required | Default Value      |
|------------|-----------------------------------------------|----------|-------------------|
| message    | Human-readable error message                  | Yes      | N/A               |
| code       | Error code for programmatic handling          | No       | "error"           |
| status_code| HTTP status code                              | No       | 400 (Bad Request) |
| details    | Additional error details                      | No       | None              |

## Benefits

1. **Consistency**: All API endpoints return responses in the same format
2. **Simplicity**: Frontend code can expect and handle responses in a predictable way
3. **Maintainability**: Centralized response formatting logic
4. **Better error handling**: Detailed error information helps debug and handle errors properly

## HTTP Status Codes

Common status codes used in the application:

| Status Code | Description           | Usage                                     |
|-------------|-----------------------|-------------------------------------------|
| 200         | OK                    | Successful GET, PUT, PATCH                |
| 201         | Created               | Successful resource creation (POST)       |
| 204         | No Content            | Successful deletion                       |
| 400         | Bad Request           | Invalid input or validation errors        |
| 401         | Unauthorized          | Authentication required                   |
| 403         | Forbidden             | Authenticated but not authorized          |
| 404         | Not Found             | Resource not found                        |
| 500         | Internal Server Error | Server-side errors                        | 