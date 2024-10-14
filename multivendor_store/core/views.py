from django.shortcuts import render

def home(request):
    return render(request, 'core/home.html')

def product_list(request):
    # This is a placeholder. We'll replace it with actual product data later.
    products = [
        {'name': 'T-Shirt', 'description': 'Comfortable cotton t-shirt', 'price': 19.99, 'vendor': {'name': 'Fashion Co.'}},
        {'name': 'Jeans', 'description': 'Classic blue jeans', 'price': 49.99, 'vendor': {'name': 'Denim World'}},
        {'name': 'Sneakers', 'description': 'Sporty sneakers', 'price': 79.99, 'vendor': {'name': 'Footwear Inc.'}},
    ]
    return render(request, 'core/product_list.html', {'products': products})
