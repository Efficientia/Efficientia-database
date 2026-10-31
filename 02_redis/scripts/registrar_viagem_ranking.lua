-- ==============================================================================
-- SCRIPT ATÔMICO LUA: REGISTRO DE VIAGEM E ATUALIZAÇÃO DE RANKINGS
-- ==============================================================================
-- Executa em transação atômica única no Redis:
-- 1. Incrementa os contadores de viagens, embarcados e mortes no Hash do motorista.
-- 2. Incrementa o volume transportado no Sorted Set mensal (ranking de volume).
-- 3. Recalcula a taxa de mortalidade (%) e atualiza o Sorted Set de mortalidade.
--
-- KEYS[1]: Chave Hash de estatísticas (stats_motorista)
-- KEYS[2]: Chave Sorted Set de volume mensal (ranking_volume)
-- KEYS[3]: Chave Sorted Set de mortalidade mensal (ranking_mortalidade)
--
-- ARGV[1]: Identificador do motorista (motorista_id)
-- ARGV[2]: Total de animais embarcados (número inteiro)
-- ARGV[3]: Quantidade de mortes registradas (número inteiro)
-- ==============================================================================

local stats_key = KEYS[1]
local volume_key = KEYS[2]
local mortalidade_key = KEYS[3]

local motorista_id = ARGV[1]
local embarcados = tonumber(ARGV[2]) or 0
local mortos = tonumber(ARGV[3]) or 0

-- 1. Atualiza Hash de estatísticas acumuladas do motorista no mês
local novo_viagens = redis.call('HINCRBY', stats_key, 'viagens', 1)
local novo_embarcados = redis.call('HINCRBY', stats_key, 'total_embarcados', embarcados)
local novo_mortos = redis.call('HINCRBY', stats_key, 'qtd_morto', mortos)

-- 2. Atualiza pontuação de volume acumulado no Sorted Set
redis.call('ZINCRBY', volume_key, embarcados, motorista_id)

-- 3. Recalcula taxa de mortalidade percentual e atualiza Sorted Set
local taxa_mortalidade = 0.0
if novo_embarcados > 0 then
    taxa_mortalidade = (novo_mortos / novo_embarcados) * 100.0
end
redis.call('ZADD', mortalidade_key, taxa_mortalidade, motorista_id)

-- Retorna os valores consolidados: {viagens, total_embarcados, qtd_morto, taxa_mortalidade}
return {novo_viagens, novo_embarcados, novo_mortos, tostring(taxa_mortalidade)}
