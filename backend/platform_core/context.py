from .permissions import owner_organizations

def product_access(request):
    return {'product_owner': owner_organizations(request.user).exists()}
