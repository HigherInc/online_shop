import requests

res = requests.put("http://127.0.0.1:3000/api/hospital/sneakers", {"name" : "test", "price" : 800.00})
print(res.json())