-- Inserts mock restaurant + menu item data for the configured prefix.
-- Uses ${PREFIX} token which is replaced by backend/scripts/apply_migrations.py.
-- Safe to apply multiple times (inserts only if tables are empty).

DECLARE
  v_count NUMBER;
BEGIN
  SELECT COUNT(*) INTO v_count FROM ${PREFIX}_restaurant;

  IF v_count = 0 THEN
    INSERT INTO ${PREFIX}_restaurant (
      name,
      image_url,
      address_line1,
      city,
      state,
      country,
      postal_code,
      latitude,
      longitude,
      phone,
      created_at,
      updated_at
    ) VALUES (
      'Sunrise Bistro',
      'https://images.unsplash.com/photo-1521017432531-fbd92d768814?auto=format&fit=crop&w=1200&q=80',
      '101 Market Street',
      'San Francisco',
      'CA',
      'USA',
      '94105',
      37.7937000,
      -122.3967000,
      '+1-415-555-0101',
      SYSTIMESTAMP,
      SYSTIMESTAMP
    );

    INSERT INTO ${PREFIX}_restaurant (
      name,
      image_url,
      address_line1,
      city,
      state,
      country,
      postal_code,
      latitude,
      longitude,
      phone,
      created_at,
      updated_at
    ) VALUES (
      'Spice Route Kitchen',
      'https://images.unsplash.com/photo-1555396273-367ea4eb4db5?auto=format&fit=crop&w=1200&q=80',
      '22 Sunset Blvd',
      'Los Angeles',
      'CA',
      'USA',
      '90028',
      34.1016000,
      -118.3269000,
      '+1-323-555-0122',
      SYSTIMESTAMP,
      SYSTIMESTAMP
    );

    INSERT INTO ${PREFIX}_restaurant (
      name,
      image_url,
      address_line1,
      city,
      state,
      country,
      postal_code,
      latitude,
      longitude,
      phone,
      created_at,
      updated_at
    ) VALUES (
      'Green Garden Cafe',
      'https://images.unsplash.com/photo-1552566626-52f8b828add9?auto=format&fit=crop&w=1200&q=80',
      '8 Orchard Road',
      'New York',
      'NY',
      'USA',
      '10001',
      40.7505000,
      -73.9965000,
      '+1-212-555-0133',
      SYSTIMESTAMP,
      SYSTIMESTAMP
    );

    COMMIT;
  END IF;
END;
/

DECLARE
  v_count NUMBER;
  v_r1 NUMBER;
  v_r2 NUMBER;
  v_r3 NUMBER;
BEGIN
  SELECT COUNT(*) INTO v_count FROM ${PREFIX}_menu_item;

  IF v_count = 0 THEN
    SELECT MIN(id) INTO v_r1 FROM ${PREFIX}_restaurant WHERE name = 'Sunrise Bistro';
    SELECT MIN(id) INTO v_r2 FROM ${PREFIX}_restaurant WHERE name = 'Spice Route Kitchen';
    SELECT MIN(id) INTO v_r3 FROM ${PREFIX}_restaurant WHERE name = 'Green Garden Cafe';

    -- Sunrise Bistro
    INSERT INTO ${PREFIX}_menu_item (restaurant_id, name, image_url, description, category, price, currency, available, created_at, updated_at)
    VALUES (v_r1, 'Avocado Toast', 'https://images.unsplash.com/photo-1541519227354-08fa5d50c44d?auto=format&fit=crop&w=1200&q=80', 'Sourdough toast with smashed avocado, lemon, and chili flakes.', 'Breakfast', 9.50, 'USD', 'Y', SYSTIMESTAMP, SYSTIMESTAMP);

    INSERT INTO ${PREFIX}_menu_item (restaurant_id, name, image_url, description, category, price, currency, available, created_at, updated_at)
    VALUES (v_r1, 'Greek Yogurt Parfait', 'https://images.unsplash.com/photo-1511690743698-d9d85f2fbf38?auto=format&fit=crop&w=1200&q=80', 'Greek yogurt with berries, granola, and honey.', 'Breakfast', 7.75, 'USD', 'Y', SYSTIMESTAMP, SYSTIMESTAMP);

    INSERT INTO ${PREFIX}_menu_item (restaurant_id, name, image_url, description, category, price, currency, available, created_at, updated_at)
    VALUES (v_r1, 'Salmon Quinoa Bowl', 'https://images.unsplash.com/photo-1512621776951-a57141f2eefd?auto=format&fit=crop&w=1200&q=80', 'Roasted salmon over quinoa with mixed greens and citrus vinaigrette.', 'Lunch', 14.95, 'USD', 'Y', SYSTIMESTAMP, SYSTIMESTAMP);

    -- Spice Route Kitchen
    INSERT INTO ${PREFIX}_menu_item (restaurant_id, name, image_url, description, category, price, currency, available, created_at, updated_at)
    VALUES (v_r2, 'Chicken Tikka Bowl', 'https://images.unsplash.com/photo-1604908177225-6fbb3cfca1f8?auto=format&fit=crop&w=1200&q=80', 'Grilled chicken tikka with basmati rice and cucumber raita.', 'Main', 15.50, 'USD', 'Y', SYSTIMESTAMP, SYSTIMESTAMP);

    INSERT INTO ${PREFIX}_menu_item (restaurant_id, name, image_url, description, category, price, currency, available, created_at, updated_at)
    VALUES (v_r2, 'Chana Masala', 'https://images.unsplash.com/photo-1606491956689-2ea866880c84?auto=format&fit=crop&w=1200&q=80', 'Chickpeas simmered in tomato-onion masala; vegan.', 'Main', 12.25, 'USD', 'Y', SYSTIMESTAMP, SYSTIMESTAMP);

    INSERT INTO ${PREFIX}_menu_item (restaurant_id, name, image_url, description, category, price, currency, available, created_at, updated_at)
    VALUES (v_r2, 'Mango Lassi', 'https://images.unsplash.com/photo-1623942710124-8941d5d295df?auto=format&fit=crop&w=1200&q=80', 'Sweet mango yogurt drink.', 'Drinks', 4.75, 'USD', 'Y', SYSTIMESTAMP, SYSTIMESTAMP);

    -- Green Garden Cafe
    INSERT INTO ${PREFIX}_menu_item (restaurant_id, name, image_url, description, category, price, currency, available, created_at, updated_at)
    VALUES (v_r3, 'Kale Caesar Salad', 'https://images.unsplash.com/photo-1556911220-e15b29be8c77?auto=format&fit=crop&w=1200&q=80', 'Kale, parmesan, croutons, and house Caesar dressing.', 'Salads', 11.95, 'USD', 'Y', SYSTIMESTAMP, SYSTIMESTAMP);

    INSERT INTO ${PREFIX}_menu_item (restaurant_id, name, image_url, description, category, price, currency, available, created_at, updated_at)
    VALUES (v_r3, 'Veggie Wrap', 'https://images.unsplash.com/photo-1550317138-10000687a72b?auto=format&fit=crop&w=1200&q=80', 'Whole wheat wrap with hummus, roasted veggies, and greens.', 'Lunch', 10.50, 'USD', 'Y', SYSTIMESTAMP, SYSTIMESTAMP);

    INSERT INTO ${PREFIX}_menu_item (restaurant_id, name, image_url, description, category, price, currency, available, created_at, updated_at)
    VALUES (v_r3, 'Berry Smoothie', 'https://images.unsplash.com/photo-1553530664-bfd7bafad7f9?auto=format&fit=crop&w=1200&q=80', 'Mixed berry smoothie with banana and chia.', 'Drinks', 6.25, 'USD', 'Y', SYSTIMESTAMP, SYSTIMESTAMP);

    COMMIT;
  END IF;
END;
/
