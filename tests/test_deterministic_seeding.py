"""Test deterministic seeding functionality."""

import random
from faker import Faker
from app.services.seeder import seed_random_generators


class TestDeterministicSeeding:
    """Test that seeding produces deterministic results."""

    def test_random_seed_deterministic(self):
        """Test that random.seed produces deterministic results."""
        # First run
        random.seed(1337)
        values1 = [random.randint(1, 100) for _ in range(10)]
        
        # Second run
        random.seed(1337)
        values2 = [random.randint(1, 100) for _ in range(10)]
        
        # Should be identical
        assert values1 == values2

    def test_faker_seed_deterministic(self):
        """Test that Faker.seed produces deterministic results."""
        # First run
        fake1 = Faker()
        fake1.seed_instance(1337)
        names1 = [fake1.user_name() for _ in range(5)]
        
        # Second run
        fake2 = Faker()
        fake2.seed_instance(1337)
        names2 = [fake2.user_name() for _ in range(5)]
        
        # Should be identical
        assert names1 == names2

    def test_seed_random_generators_function(self):
        """Test that our seed_random_generators function works correctly."""
        # First run
        seed_random_generators()
        fake = Faker()
        fake.seed_instance(1337)
        
        random_values1 = [random.randint(1, 100) for _ in range(5)]
        fake_names1 = [fake.user_name() for _ in range(3)]
        
        # Second run
        seed_random_generators()
        fake = Faker()
        fake.seed_instance(1337)
        
        random_values2 = [random.randint(1, 100) for _ in range(5)]
        fake_names2 = [fake.user_name() for _ in range(3)]
        
        # Should be identical
        assert random_values1 == random_values2
        assert fake_names1 == fake_names2

    def test_seeding_produces_expected_values(self):
        """Test that seeding produces known expected values."""
        # Test with known seed to verify deterministic behavior
        random.seed(1337)
        fake = Faker()
        fake.seed_instance(1337)
        
        # These should be the first values generated with seed 1337
        first_random = random.randint(1, 100)
        first_name = fake.user_name()
        
        # Reset and check again
        random.seed(1337)
        fake = Faker()
        fake.seed_instance(1337)
        
        assert random.randint(1, 100) == first_random
        assert fake.user_name() == first_name