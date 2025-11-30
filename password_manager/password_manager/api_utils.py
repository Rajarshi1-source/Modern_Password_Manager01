from rest_framework.response import Response
from rest_framework import status

def error_response(message, status_code=status.HTTP_400_BAD_REQUEST, code="error", details=None):
    """Helper function to create standardized error responses"""
    return Response({
        "success": False,
        "message": message,
        "code": code,
        "details": details or {}
    }, status=status_code)

def success_response(data=None, message="Operation successful", status_code=status.HTTP_200_OK):
    """Helper function to create standardized success responses"""
    response = {
        "success": True,
        "message": message,
    }
    
    if data is not None:
        if isinstance(data, dict):
            response.update(data)
        else:
            response["data"] = data
            
    return Response(response, status=status_code) 