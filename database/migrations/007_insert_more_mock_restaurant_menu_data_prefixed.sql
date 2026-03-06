-- Inserts MORE mock restaurant + menu item data for the configured prefix.
-- Uses ${PREFIX} token which is replaced by backend/scripts/apply_migrations.py.
-- Safe to apply multiple times: inserts each restaurant/menu item only if it doesn't already exist.

DECLARE
  v_exists NUMBER;
BEGIN
  -- Restaurants (dedupe by name + city + address_line1)

  SELECT COUNT(*) INTO v_exists
  FROM ${PREFIX}_restaurant
  WHERE name = 'Harborview Seafood' AND city = 'San Francisco' AND address_line1 = '2 Embarcadero Center';

  IF v_exists = 0 THEN
    INSERT INTO ${PREFIX}_restaurant (
      name, image_url,
      address_line1, city, state, country, postal_code,
      latitude, longitude, phone,
      created_at, updated_at
    ) VALUES (
      'Harborview Seafood',
      'https://images.unsplash.com/photo-1559339352-11d035aa65de?auto=format&fit=crop&w=1200&q=80',
      '2 Embarcadero Center',
      'San Francisco',
      'CA',
      'USA',
      '94111',
      37.7952000,
      -122.3970000,
      '+1-415-555-0201',
      SYSTIMESTAMP,
      SYSTIMESTAMP
    );
  END IF;

  SELECT COUNT(*) INTO v_exists
  FROM ${PREFIX}_restaurant
  WHERE name = 'Mission Street Tacos' AND city = 'San Francisco' AND address_line1 = '3251 16th Street';

  IF v_exists = 0 THEN
    INSERT INTO ${PREFIX}_restaurant (
      name, image_url,
      address_line1, city, state, country, postal_code,
      latitude, longitude, phone,
      created_at, updated_at
    ) VALUES (
      'Mission Street Tacos',
      'https://images.unsplash.com/photo-1555396273-367ea4eb4db5?auto=format&fit=crop&w=1200&q=80',
      '3251 16th Street',
      'San Francisco',
      'CA',
      'USA',
      '94110',
      37.7646000,
      -122.4210000,
      '+1-415-555-0202',
      SYSTIMESTAMP,
      SYSTIMESTAMP
    );
  END IF;

  SELECT COUNT(*) INTO v_exists
  FROM ${PREFIX}_restaurant
  WHERE name = 'Downtown Ramen House' AND city = 'Los Angeles' AND address_line1 = '430 W 6th Street';

  IF v_exists = 0 THEN
    INSERT INTO ${PREFIX}_restaurant (
      name, image_url,
      address_line1, city, state, country, postal_code,
      latitude, longitude, phone,
      created_at, updated_at
    ) VALUES (
      'Downtown Ramen House',
      'https://images.unsplash.com/photo-1540189549336-e6e99c3679fe?auto=format&fit=crop&w=1200&q=80',
      '430 W 6th Street',
      'Los Angeles',
      'CA',
      'USA',
      '90014',
      34.0467000,
      -118.2547000,
      '+1-323-555-0203',
      SYSTIMESTAMP,
      SYSTIMESTAMP
    );
  END IF;

  SELECT COUNT(*) INTO v_exists
  FROM ${PREFIX}_restaurant
  WHERE name = 'Brooklyn Brick Oven Pizza' AND city = 'New York' AND address_line1 = '210 Flatbush Avenue';

  IF v_exists = 0 THEN
    INSERT INTO ${PREFIX}_restaurant (
      name, image_url,
      address_line1, city, state, country, postal_code,
      latitude, longitude, phone,
      created_at, updated_at
    ) VALUES (
      'Brooklyn Brick Oven Pizza',
      'https://images.unsplash.com/photo-1542281286-9e0a16bb7366?auto=format&fit=crop&w=1200&q=80',
      '210 Flatbush Avenue',
      'New York',
      'NY',
      'USA',
      '11217',
      40.6847000,
      -73.9759000,
      '+1-212-555-0204',
      SYSTIMESTAMP,
      SYSTIMESTAMP
    );
  END IF;

  SELECT COUNT(*) INTO v_exists
  FROM ${PREFIX}_restaurant
  WHERE name = 'Capitol Vegan Deli' AND city = 'Austin' AND address_line1 = '110 Congress Ave';

  IF v_exists = 0 THEN
    INSERT INTO ${PREFIX}_restaurant (
      name, image_url,
      address_line1, city, state, country, postal_code,
      latitude, longitude, phone,
      created_at, updated_at
    ) VALUES (
      'Capitol Vegan Deli',
      'https://images.unsplash.com/photo-1552566626-52f8b828add9?auto=format&fit=crop&w=1200&q=80',
      '110 Congress Ave',
      'Austin',
      'TX',
      'USA',
      '78701',
      30.2636000,
      -97.7429000,
      '+1-512-555-0205',
      SYSTIMESTAMP,
      SYSTIMESTAMP
    );
  END IF;

  COMMIT;
END;
/

DECLARE
  v_exists NUMBER;
  v_rest_id NUMBER;
BEGIN
  -- Menu items (dedupe by restaurant_id + item name)

  -- Harborview Seafood
  SELECT MIN(id) INTO v_rest_id FROM ${PREFIX}_restaurant
  WHERE name = 'Harborview Seafood' AND city = 'San Francisco' AND address_line1 = '2 Embarcadero Center';

  IF v_rest_id IS NOT NULL THEN
    SELECT COUNT(*) INTO v_exists FROM ${PREFIX}_menu_item WHERE restaurant_id = v_rest_id AND name = 'Lobster Roll';
    IF v_exists = 0 THEN
      INSERT INTO ${PREFIX}_menu_item (restaurant_id, name, image_url, description, category, price, currency, available, created_at, updated_at)
      VALUES (v_rest_id, 'Lobster Roll', 'https://images.unsplash.com/photo-1553621042-f6e147245754?auto=format&fit=crop&w=1200&q=80', 'Buttery toasted bun with lobster and lemon aioli.', 'Main', 24.50, 'USD', 'Y', SYSTIMESTAMP, SYSTIMESTAMP);
    END IF;

    SELECT COUNT(*) INTO v_exists FROM ${PREFIX}_menu_item WHERE restaurant_id = v_rest_id AND name = 'Clam Chowder';
    IF v_exists = 0 THEN
      INSERT INTO ${PREFIX}_menu_item (restaurant_id, name, image_url, description, category, price, currency, available, created_at, updated_at)
      VALUES (v_rest_id, 'Clam Chowder', 'https://images.unsplash.com/photo-1604908177225-6fbb3cfca1f8?auto=format&fit=crop&w=1200&q=80', 'Creamy New England style chowder with herbs.', 'Soups', 9.95, 'USD', 'Y', SYSTIMESTAMP, SYSTIMESTAMP);
    END IF;

    SELECT COUNT(*) INTO v_exists FROM ${PREFIX}_menu_item WHERE restaurant_id = v_rest_id AND name = 'Grilled Salmon Plate';
    IF v_exists = 0 THEN
      INSERT INTO ${PREFIX}_menu_item (restaurant_id, name, image_url, description, category, price, currency, available, created_at, updated_at)
      VALUES (v_rest_id, 'Grilled Salmon Plate', 'https://images.unsplash.com/photo-1467003909585-2f8a72700288?auto=format&fit=crop&w=1200&q=80', 'Grilled salmon with seasonal vegetables and rice.', 'Main', 22.00, 'USD', 'Y', SYSTIMESTAMP, SYSTIMESTAMP);
    END IF;
  END IF;

  -- Mission Street Tacos
  SELECT MIN(id) INTO v_rest_id FROM ${PREFIX}_restaurant
  WHERE name = 'Mission Street Tacos' AND city = 'San Francisco' AND address_line1 = '3251 16th Street';

  IF v_rest_id IS NOT NULL THEN
    SELECT COUNT(*) INTO v_exists FROM ${PREFIX}_menu_item WHERE restaurant_id = v_rest_id AND name = 'Carnitas Tacos';
    IF v_exists = 0 THEN
      INSERT INTO ${PREFIX}_menu_item (restaurant_id, name, image_url, description, category, price, currency, available, created_at, updated_at)
      VALUES (v_rest_id, 'Carnitas Tacos', 'https://images.unsplash.com/photo-1552332386-f8dd00dc2f85?auto=format&fit=crop&w=1200&q=80', 'Slow-cooked pork with onion, cilantro, salsa.', 'Main', 12.50, 'USD', 'Y', SYSTIMESTAMP, SYSTIMESTAMP);
    END IF;

    SELECT COUNT(*) INTO v_exists FROM ${PREFIX}_menu_item WHERE restaurant_id = v_rest_id AND name = 'Veggie Tacos';
    IF v_exists = 0 THEN
      INSERT INTO ${PREFIX}_menu_item (restaurant_id, name, image_url, description, category, price, currency, available, created_at, updated_at)
      VALUES (v_rest_id, 'Veggie Tacos', 'https://images.unsplash.com/photo-1617196034796-73c9b54f4c41?auto=format&fit=crop&w=1200&q=80', 'Grilled veggies, black beans, pico de gallo.', 'Main', 11.00, 'USD', 'Y', SYSTIMESTAMP, SYSTIMESTAMP);
    END IF;

    SELECT COUNT(*) INTO v_exists FROM ${PREFIX}_menu_item WHERE restaurant_id = v_rest_id AND name = 'Horchata';
    IF v_exists = 0 THEN
      INSERT INTO ${PREFIX}_menu_item (restaurant_id, name, image_url, description, category, price, currency, available, created_at, updated_at)
      VALUES (v_rest_id, 'Horchata', 'https://images.unsplash.com/photo-1544145945-f90425340c7e?auto=format&fit=crop&w=1200&q=80', 'Cinnamon rice drink served cold.', 'Drinks', 4.25, 'USD', 'Y', SYSTIMESTAMP, SYSTIMESTAMP);
    END IF;
  END IF;

  -- Downtown Ramen House
  SELECT MIN(id) INTO v_rest_id FROM ${PREFIX}_restaurant
  WHERE name = 'Downtown Ramen House' AND city = 'Los Angeles' AND address_line1 = '430 W 6th Street';

  IF v_rest_id IS NOT NULL THEN
    SELECT COUNT(*) INTO v_exists FROM ${PREFIX}_menu_item WHERE restaurant_id = v_rest_id AND name = 'Tonkotsu Ramen';
    IF v_exists = 0 THEN
      INSERT INTO ${PREFIX}_menu_item (restaurant_id, name, image_url, description, category, price, currency, available, created_at, updated_at)
      VALUES (v_rest_id, 'Tonkotsu Ramen', 'https://images.unsplash.com/photo-1547928575-1a4f68a66f77?auto=format&fit=crop&w=1200&q=80', 'Pork bone broth ramen with chashu and egg.', 'Main', 16.75, 'USD', 'Y', SYSTIMESTAMP, SYSTIMESTAMP);
    END IF;

    SELECT COUNT(*) INTO v_exists FROM ${PREFIX}_menu_item WHERE restaurant_id = v_rest_id AND name = 'Spicy Miso Ramen';
    IF v_exists = 0 THEN
      INSERT INTO ${PREFIX}_menu_item (restaurant_id, name, image_url, description, category, price, currency, available, created_at, updated_at)
      VALUES (v_rest_id, 'Spicy Miso Ramen', 'https://images.unsplash.com/photo-1617093727343-374698b1b08d?auto=format&fit=crop&w=1200&q=80', 'Miso broth with chili, corn, and bamboo shoots.', 'Main', 17.25, 'USD', 'Y', SYSTIMESTAMP, SYSTIMESTAMP);
    END IF;

    SELECT COUNT(*) INTO v_exists FROM ${PREFIX}_menu_item WHERE restaurant_id = v_rest_id AND name = 'Matcha Iced Tea';
    IF v_exists = 0 THEN
      INSERT INTO ${PREFIX}_menu_item (restaurant_id, name, image_url, description, category, price, currency, available, created_at, updated_at)
      VALUES (v_rest_id, 'Matcha Iced Tea', 'https://images.unsplash.com/photo-1517701604599-bb29b565090c?auto=format&fit=crop&w=1200&q=80', 'Iced matcha green tea lightly sweetened.', 'Drinks', 5.25, 'USD', 'Y', SYSTIMESTAMP, SYSTIMESTAMP);
    END IF;
  END IF;

  -- Brooklyn Brick Oven Pizza
  SELECT MIN(id) INTO v_rest_id FROM ${PREFIX}_restaurant
  WHERE name = 'Brooklyn Brick Oven Pizza' AND city = 'New York' AND address_line1 = '210 Flatbush Avenue';

  IF v_rest_id IS NOT NULL THEN
    SELECT COUNT(*) INTO v_exists FROM ${PREFIX}_menu_item WHERE restaurant_id = v_rest_id AND name = 'Margherita Pizza';
    IF v_exists = 0 THEN
      INSERT INTO ${PREFIX}_menu_item (restaurant_id, name, image_url, description, category, price, currency, available, created_at, updated_at)
      VALUES (v_rest_id, 'Margherita Pizza', 'https://images.unsplash.com/photo-1548365328-8b849e6f14c9?auto=format&fit=crop&w=1200&q=80', 'Tomato, mozzarella, basil; brick-oven baked.', 'Main', 18.00, 'USD', 'Y', SYSTIMESTAMP, SYSTIMESTAMP);
    END IF;

    SELECT COUNT(*) INTO v_exists FROM ${PREFIX}_menu_item WHERE restaurant_id = v_rest_id AND name = 'Pepperoni Pizza';
    IF v_exists = 0 THEN
      INSERT INTO ${PREFIX}_menu_item (restaurant_id, name, image_url, description, category, price, currency, available, created_at, updated_at)
      VALUES (v_rest_id, 'Pepperoni Pizza', 'https://images.unsplash.com/photo-1601924928376-3ec7be5b6e49?auto=format&fit=crop&w=1200&q=80', 'Classic pepperoni with mozzarella and oregano.', 'Main', 19.50, 'USD', 'Y', SYSTIMESTAMP, SYSTIMESTAMP);
    END IF;

    SELECT COUNT(*) INTO v_exists FROM ${PREFIX}_menu_item WHERE restaurant_id = v_rest_id AND name = 'House Lemonade';
    IF v_exists = 0 THEN
      INSERT INTO ${PREFIX}_menu_item (restaurant_id, name, image_url, description, category, price, currency, available, created_at, updated_at)
      VALUES (v_rest_id, 'House Lemonade', 'https://images.unsplash.com/photo-1497534446932-c925b458314e?auto=format&fit=crop&w=1200&q=80', 'Fresh squeezed lemonade.', 'Drinks', 4.95, 'USD', 'Y', SYSTIMESTAMP, SYSTIMESTAMP);
    END IF;
  END IF;

  -- Capitol Vegan Deli
  SELECT MIN(id) INTO v_rest_id FROM ${PREFIX}_restaurant
  WHERE name = 'Capitol Vegan Deli' AND city = 'Austin' AND address_line1 = '110 Congress Ave';

  IF v_rest_id IS NOT NULL THEN
    SELECT COUNT(*) INTO v_exists FROM ${PREFIX}_menu_item WHERE restaurant_id = v_rest_id AND name = 'Chickpea Salad Sandwich';
    IF v_exists = 0 THEN
      INSERT INTO ${PREFIX}_menu_item (restaurant_id, name, image_url, description, category, price, currency, available, created_at, updated_at)
      VALUES (v_rest_id, 'Chickpea Salad Sandwich', 'https://images.unsplash.com/photo-1525351484163-7529414344d8?auto=format&fit=crop&w=1200&q=80', 'Mashed chickpeas with celery on toasted bread.', 'Lunch', 12.00, 'USD', 'Y', SYSTIMESTAMP, SYSTIMESTAMP);
    END IF;

    SELECT COUNT(*) INTO v_exists FROM ${PREFIX}_menu_item WHERE restaurant_id = v_rest_id AND name = 'Vegan Reuben';
    IF v_exists = 0 THEN
      INSERT INTO ${PREFIX}_menu_item (restaurant_id, name, image_url, description, category, price, currency, available, created_at, updated_at)
      VALUES (v_rest_id, 'Vegan Reuben', 'https://images.unsplash.com/photo-1550547660-d9450f859349?auto=format&fit=crop&w=1200&q=80', 'Plant-based reuben with sauerkraut and dressing.', 'Lunch', 13.50, 'USD', 'Y', SYSTIMESTAMP, SYSTIMESTAMP);
    END IF;

    SELECT COUNT(*) INTO v_exists FROM ${PREFIX}_menu_item WHERE restaurant_id = v_rest_id AND name = 'Cold Brew Coffee';
    IF v_exists = 0 THEN
      INSERT INTO ${PREFIX}_menu_item (restaurant_id, name, image_url, description, category, price, currency, available, created_at, updated_at)
      VALUES (v_rest_id, 'Cold Brew Coffee', 'https://images.unsplash.com/photo-1511920170033-f8396924c348?auto=format&fit=crop&w=1200&q=80', 'Smooth cold brew served over ice.', 'Drinks', 4.75, 'USD', 'Y', SYSTIMESTAMP, SYSTIMESTAMP);
    END IF;
  END IF;

  COMMIT;
END;
/
