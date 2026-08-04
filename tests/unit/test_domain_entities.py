"""
Unit tests for domain entities — User and Product aggregate roots.
No external dependencies required.
"""
from decimal import Decimal

from app.domain.entities.product import Product
from app.domain.entities.user import User
from app.domain.events import (
    ProductCreatedEvent,
    ProductUpdatedEvent,
    UserRegisteredEvent,
    UserUpdatedEvent,
)
from app.domain.exceptions import DomainErrorCode


class TestUserEntity:
    def test_create_user_success(self):
        result = User.create(
            email="alice@example.com",
            hashed_password="hashed_pw",
            full_name="Alice Smith",
        )
        assert result.is_ok()
        user = result.unwrap()
        assert str(user.email) == "alice@example.com"
        assert user.full_name == "Alice Smith"
        assert user.is_active is True
        assert user.is_superuser is False
        assert user.id is None

    def test_create_user_normalizes_email(self):
        result = User.create(
            email="  ALICE@EXAMPLE.COM  ",
            hashed_password="hashed_pw",
            full_name="Alice",
        )
        assert result.is_ok()
        assert str(result.unwrap().email) == "alice@example.com"

    def test_create_user_empty_email_fails(self):
        result = User.create(email="", hashed_password="hashed_pw", full_name="Alice")
        assert result.is_err()
        assert result.unwrap_err().code == DomainErrorCode.VALIDATION_ERROR

    def test_create_user_invalid_email_format_fails(self):
        result = User.create(email="not-an-email", hashed_password="hashed_pw", full_name="Alice")
        assert result.is_err()
        assert result.unwrap_err().code == DomainErrorCode.VALIDATION_ERROR

    def test_create_user_empty_password_fails(self):
        result = User.create(email="alice@example.com", hashed_password="", full_name="Alice")
        assert result.is_err()

    def test_create_user_empty_full_name_fails(self):
        result = User.create(email="alice@example.com", hashed_password="hashed_pw", full_name="")
        assert result.is_err()

    def test_create_user_does_not_emit_events(self):
        """create() can't know the real id yet (None until persisted) — mark_registered()
        is what queues the event, called by the repository after the INSERT flush."""
        result = User.create(
            email="alice@example.com", hashed_password="hashed_pw", full_name="Alice"
        )
        user = result.unwrap()
        assert user.collect_events() == []

    def test_mark_registered_emits_user_registered_event(self):
        result = User.create(
            email="alice@example.com", hashed_password="hashed_pw", full_name="Alice"
        )
        user = result.unwrap()
        user.id = 42
        user.mark_registered()
        events = user.collect_events()
        assert len(events) == 1
        assert isinstance(events[0], UserRegisteredEvent)
        assert events[0].user_id == 42
        assert events[0].email == "alice@example.com"
        # collect_events() drains the queue
        assert user.collect_events() == []

    def test_update_profile_success(self):
        result = User.create(
            email="alice@example.com",
            hashed_password="hashed_pw",
            full_name="Alice Smith",
        )
        user = result.unwrap()
        update_result = user.update_profile(full_name="Alice Johnson")
        assert update_result.is_ok()
        assert user.full_name == "Alice Johnson"

    def test_update_profile_emits_user_updated_event(self):
        result = User.create(
            email="alice@example.com", hashed_password="hashed_pw", full_name="Alice"
        )
        user = result.unwrap()
        user.id = 7
        user.update_profile(full_name="Alice Updated")
        events = user.collect_events()
        assert len(events) == 1
        assert isinstance(events[0], UserUpdatedEvent)
        assert events[0].user_id == 7

    def test_update_profile_empty_name_fails(self):
        result = User.create(
            email="alice@example.com",
            hashed_password="hashed_pw",
            full_name="Alice Smith",
        )
        user = result.unwrap()
        update_result = user.update_profile(full_name="   ")
        assert update_result.is_err()

    def test_deactivate_user(self):
        result = User.create(
            email="alice@example.com",
            hashed_password="hashed_pw",
            full_name="Alice Smith",
        )
        user = result.unwrap()
        assert user.is_active is True
        user.deactivate()
        assert user.is_active is False

    def test_activate_user(self):
        result = User.create(
            email="alice@example.com",
            hashed_password="hashed_pw",
            full_name="Alice Smith",
        )
        user = result.unwrap()
        user.deactivate()
        user.activate()
        assert user.is_active is True


class TestProductEntity:
    def test_create_product_success(self):
        result = Product.create(
            name="Wireless Headphones",
            description="Great headphones",
            price=99.99,
            stock=50,
            owner_id=1,
        )
        assert result.is_ok()
        product = result.unwrap()
        assert str(product.name) == "Wireless Headphones"
        assert product.price.amount == Decimal("99.99")
        assert product.stock == 50
        assert product.owner_id == 1
        assert product.id is None

    def test_create_product_negative_price_fails(self):
        result = Product.create(
            name="Test", description="", price=-1.0, stock=10, owner_id=1
        )
        assert result.is_err()
        assert result.unwrap_err().code == DomainErrorCode.VALIDATION_ERROR

    def test_create_product_negative_stock_fails(self):
        result = Product.create(
            name="Test", description="", price=10.0, stock=-1, owner_id=1
        )
        assert result.is_err()

    def test_create_product_empty_name_fails(self):
        result = Product.create(
            name="", description="", price=10.0, stock=10, owner_id=1
        )
        assert result.is_err()

    def test_create_product_invalid_owner_fails(self):
        result = Product.create(
            name="Test", description="", price=10.0, stock=10, owner_id=0
        )
        assert result.is_err()

    def test_create_product_price_is_exact_decimal(self):
        """0.1 + 0.2 != 0.3 in float — Money must not inherit that drift."""
        result = Product.create(
            name="Test", description="", price="19.99", stock=1, owner_id=1
        )
        product = result.unwrap()
        assert product.price.amount + product.price.amount == Decimal("39.98")

    def test_mark_created_emits_product_created_event(self):
        result = Product.create(
            name="Headphones", description="", price=99.99, stock=50, owner_id=1
        )
        product = result.unwrap()
        product.id = 5
        product.mark_created()
        events = product.collect_events()
        assert len(events) == 1
        assert isinstance(events[0], ProductCreatedEvent)
        assert events[0].product_id == 5
        assert events[0].owner_id == 1
        assert events[0].name == "Headphones"

    def test_update_product_success(self):
        result = Product.create(
            name="Headphones", description="", price=99.99, stock=50, owner_id=1
        )
        product = result.unwrap()
        update_result = product.update(name="Premium Headphones", price=129.99)
        assert update_result.is_ok()
        assert str(product.name) == "Premium Headphones"
        assert product.price.amount == Decimal("129.99")

    def test_update_product_emits_product_updated_event(self):
        result = Product.create(
            name="Headphones", description="", price=99.99, stock=50, owner_id=1
        )
        product = result.unwrap()
        product.id = 9
        product.update(price=79.99)
        events = product.collect_events()
        assert len(events) == 1
        assert isinstance(events[0], ProductUpdatedEvent)
        assert events[0].product_id == 9

    def test_reduce_stock_success(self):
        result = Product.create(
            name="Headphones", description="", price=99.99, stock=50, owner_id=1
        )
        product = result.unwrap()
        reduce_result = product.reduce_stock(10)
        assert reduce_result.is_ok()
        assert product.stock == 40

    def test_reduce_stock_insufficient_fails(self):
        result = Product.create(
            name="Headphones", description="", price=99.99, stock=5, owner_id=1
        )
        product = result.unwrap()
        reduce_result = product.reduce_stock(10)
        assert reduce_result.is_err()
        assert reduce_result.unwrap_err().code == DomainErrorCode.INSUFFICIENT_STOCK

    def test_reduce_stock_zero_quantity_fails(self):
        result = Product.create(
            name="Headphones", description="", price=99.99, stock=50, owner_id=1
        )
        product = result.unwrap()
        reduce_result = product.reduce_stock(0)
        assert reduce_result.is_err()
