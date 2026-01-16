"""
Custom exceptions for Lead Genius API.
Provides consistent error handling across the application.
"""
from fastapi import HTTPException, status


class LeadGeniusException(Exception):
    """Base exception for Lead Genius"""
    def __init__(self, message: str = "An error occurred"):
        self.message = message
        super().__init__(self.message)


class NotFoundError(LeadGeniusException):
    """Resource not found"""
    def __init__(self, resource: str = "Resource", resource_id: str = None):
        message = f"{resource} not found"
        if resource_id:
            message = f"{resource} with id '{resource_id}' not found"
        super().__init__(message)


class AlreadyExistsError(LeadGeniusException):
    """Resource already exists"""
    def __init__(self, resource: str = "Resource", field: str = None, value: str = None):
        if field and value:
            message = f"{resource} with {field} '{value}' already exists"
        else:
            message = f"{resource} already exists"
        super().__init__(message)


class UnauthorizedError(LeadGeniusException):
    """Authentication failed"""
    def __init__(self, message: str = "Could not validate credentials"):
        super().__init__(message)


class ForbiddenError(LeadGeniusException):
    """Access denied"""
    def __init__(self, message: str = "You don't have permission to access this resource"):
        super().__init__(message)


class ValidationError(LeadGeniusException):
    """Validation failed"""
    def __init__(self, message: str = "Validation failed", field: str = None):
        if field:
            message = f"Validation failed for field '{field}': {message}"
        super().__init__(message)


class TokenExpiredError(LeadGeniusException):
    """Token has expired"""
    def __init__(self, token_type: str = "Token"):
        super().__init__(f"{token_type} has expired")


class TokenInvalidError(LeadGeniusException):
    """Token is invalid"""
    def __init__(self, token_type: str = "Token"):
        super().__init__(f"{token_type} is invalid")


class ExternalServiceError(LeadGeniusException):
    """External service call failed"""
    def __init__(self, service: str = "External service", message: str = None):
        msg = f"{service} call failed"
        if message:
            msg = f"{msg}: {message}"
        super().__init__(msg)


# HTTP Exception helpers
def raise_not_found(resource: str = "Resource", resource_id: str = None):
    """Raise 404 HTTPException"""
    err = NotFoundError(resource, resource_id)
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=err.message)


def raise_already_exists(resource: str = "Resource", field: str = None, value: str = None):
    """Raise 400 HTTPException for duplicate"""
    err = AlreadyExistsError(resource, field, value)
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err.message)


def raise_unauthorized(message: str = "Could not validate credentials"):
    """Raise 401 HTTPException"""
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=message,
        headers={"WWW-Authenticate": "Bearer"},
    )


def raise_forbidden(message: str = "You don't have permission to access this resource"):
    """Raise 403 HTTPException"""
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=message)


def raise_validation_error(message: str = "Validation failed", field: str = None):
    """Raise 422 HTTPException"""
    err = ValidationError(message, field)
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=err.message)
