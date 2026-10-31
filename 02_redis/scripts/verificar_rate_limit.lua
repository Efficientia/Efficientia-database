-- ==============================================================================
-- SCRIPT ATÔMICO LUA: LIMITAÇÃO DE REQUISIÇÕES (RATE LIMITING)
-- ==============================================================================
-- Controla a taxa de requisições por janela temporal (Fixed Window / Sliding)
-- de maneira atômica, evitando condições de corrida em ambientes distribuídos.
--
-- KEYS[1]: Chave de identificação da janela do cliente (ex: ratelimit:user_id:endpoint)
-- ARGV[1]: Limite máximo permitido de requisições na janela (ex: 100)
-- ARGV[2]: Duração da janela temporal em segundos (TTL, ex: 60)
--
-- Retorno: Array com 4 elementos:
--   [1] Total de requisições já efetuadas na janela (número)
--   [2] Status de autorização (1 = Permitido, 0 = Bloqueado por excesso)
--   [3] Requisições restantes permitidas (número)
--   [4] TTL restante da janela em segundos
-- ==============================================================================

local key = KEYS[1]
local limit = tonumber(ARGV[1])
local window = tonumber(ARGV[2])

local current = redis.call('INCR', key)

if current == 1 then
    redis.call('EXPIRE', key, window)
end

local ttl = redis.call('TTL', key)
local allowed = 0
local remaining = 0

if current <= limit then
    allowed = 1
    remaining = limit - current
else
    allowed = 0
    remaining = 0
end

return {current, allowed, remaining, ttl}
