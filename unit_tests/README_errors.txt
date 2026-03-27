# Parser error fixtures for manual testing.
# Each file below is intentionally invalid and should raise ParsingError.
#
# error_negative_drones.txt            -> Number of drones can not be negative
# error_invalid_zone_type.txt          -> invalid zone enum value
# error_invalid_hub_metadata_key.txt   -> invalid metadata key on hub
# error_invalid_conn_metadata_key.txt  -> invalid metadata key on connection
# error_nonint_max_drones.txt          -> 'max_drones' must be an integer
# error_zero_max_drones.txt            -> 'max_drones' must be positive
# error_nonint_link_capacity.txt       -> 'max_link_capacity' must be an integer
# error_self_connection.txt            -> self connection forbidden
# error_duplicate_connection.txt       -> duplicate undirected connection
# error_missing_equals_in_metadata.txt -> malformed metadata token (no '=')
#
# Reference valid maps:
# - test_map.txt
# - two_zones_valid.txt
