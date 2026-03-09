# Normal code
user_id = "uuid-123e4567-e89b-12d3-a456-426614174000"          # hex-like, but no keyword → should skip

# Real candidate
API_SECRET = "v2.local.r8xK2y2u5zK9pQvL_wv63Gi4Tv7vD5v_extra_stuff_here"

# Fake in test
TEST_TOKEN = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"      # high entropy but in TEST_ → maybe still flag or not

# URL with base64 junk
image = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="