from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.core.models import Category, Subcategory, Product
from apps.orders.models import Cart, CartItem
from apps.users.models import User


class UserLocationAPITestCase(APITestCase):
	def setUp(self):
		self.user = User.objects.create_user(
			phone_number="+998900000001",
			password="pass1234",
			first_name="Test",
			last_name="User",
		)
		self.client.force_authenticate(user=self.user)
		self.url = reverse("user-location")

	def test_get_and_update_location(self):
		response = self.client.get(self.url)
		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data["location_street"], "")

		payload = {
			"location_label": "Home",
			"location_street": "Main street",
			"location_building": "12",
			"location_apartment": "34",
			"location_latitude": "41.299495",
			"location_longitude": "69.240074",
		}
		response = self.client.put(self.url, payload, format="json")
		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.user.refresh_from_db()
		self.assertEqual(self.user.location_street, "Main street")
		self.assertEqual(self.user.location_label, "Home")

		response = self.client.get(self.url)
		self.assertEqual(response.data["location_label"], "Home")


class OrderLocationRequirementTestCase(APITestCase):
	def setUp(self):
		self.user = User.objects.create_user(
			phone_number="+998900000002",
			password="pass1234",
			first_name="Buyer",
			last_name="Test",
		)
		self.client.force_authenticate(user=self.user)
		category = Category.objects.create(name="Fruits")
		subcategory = Subcategory.objects.create(name="Apples", category=category)
		image = SimpleUploadedFile("apple.jpg", b"filecontent", content_type="image/jpeg")
		product = Product.objects.create(
			name="Apple",
			subcategory=subcategory,
			image=image,
			price=Decimal("10.00"),
			unit="piece",
		)
		cart = Cart.objects.create(user=self.user)
		CartItem.objects.create(cart=cart, product=product, quantity=1)
		self.url = reverse("create-order")

	def test_cannot_use_saved_location_if_not_set(self):
		response = self.client.post(self.url, {"use_saved_location": True}, format="json")
		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

		self.user.update_saved_location(
			address_street="Main street",
			address_building="12",
			address_apartment="34",
		)

		response = self.client.post(self.url, {"use_saved_location": True}, format="json")
		self.assertEqual(response.status_code, status.HTTP_201_CREATED)

	def test_remember_location_flag_persists_address(self):
		payload = {
			"address_street": "Main street",
			"address_building": "12",
			"address_apartment": "34",
			"remember_location": True,
		}
		response = self.client.post(self.url, payload, format="json")
		self.assertEqual(response.status_code, status.HTTP_201_CREATED)

		self.user.refresh_from_db()
		self.assertEqual(self.user.location_street, "Main street")
		self.assertEqual(self.user.location_building, "12")
