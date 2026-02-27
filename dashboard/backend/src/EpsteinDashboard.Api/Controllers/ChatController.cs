using System.Text;
using System.Text.Json;
using AutoMapper;
using EpsteinDashboard.Application.DTOs;
using EpsteinDashboard.Core.Interfaces;
using EpsteinDashboard.Core.Models;
using Microsoft.AspNetCore.Mvc;

namespace EpsteinDashboard.Api.Controllers;

[ApiController]
[Route("api/[controller]")]
public class ChatController : ControllerBase
{
    private readonly IChunkSearchService _chunkSearchService;
    private readonly IConfiguration _configuration;
    private readonly IMapper _mapper;
    private readonly ILogger<ChatController> _logger;
    private readonly HttpClient _httpClient;

    public ChatController(
        IChunkSearchService chunkSearchService,
        IConfiguration configuration,
        IMapper mapper,
        ILogger<ChatController> logger,
        IHttpClientFactory httpClientFactory)
    {
        _chunkSearchService = chunkSearchService;
        _configuration = configuration;
        _mapper = mapper;
        _logger = logger;
        _httpClient = httpClientFactory.CreateClient("OpenAI");
    }

    public class ChatRequest
    {
        public string Message { get; set; } = string.Empty;
        public List<ChatHistoryItem>? History { get; set; }
        public int MaxChunks { get; set; } = 8;
        public double MinRelevanceScore { get; set; } = 0.25;
    }

    public class ChatHistoryItem
    {
        public string Role { get; set; } = string.Empty;
        public string Content { get; set; } = string.Empty;
    }

    public class ChatResponse
    {
        public string Answer { get; set; } = string.Empty;
        public List<ChunkSearchResultDto> Sources { get; set; } = new();
        public TokenUsage? TokensUsed { get; set; }
    }

    public class TokenUsage
    {
        public int Input { get; set; }
        public int Output { get; set; }
    }

    [HttpPost("completion")]
    public async Task<ActionResult<ChatResponse>> GetCompletion(
        [FromBody] ChatRequest request,
        CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrWhiteSpace(request.Message))
        {
            return BadRequest("Message is required.");
        }

        var apiKey = _configuration["OpenAI:ApiKey"]
            ?? Environment.GetEnvironmentVariable("OPENAI_API_KEY");

        if (string.IsNullOrWhiteSpace(apiKey))
        {
            _logger.LogWarning("OpenAI API key not configured");
            return StatusCode(503, "AI service not configured. Please set OPENAI_API_KEY.");
        }

        try
        {
            // 1. Generate embedding for the user's question (standard RAG approach)
            var queryEmbedding = await GetQueryEmbeddingAsync(request.Message, apiKey, cancellationToken);
            _logger.LogInformation("Generated {Dimensions}-dimensional embedding for query",
                queryEmbedding?.Length ?? 0);

            // 2. Search for relevant chunks using semantic vector search
            var chunks = new List<ChunkSearchResult>();
            try
            {
                var searchRequest = new ChunkSearchRequest
                {
                    Query = request.Message,
                    Page = 0,
                    PageSize = request.MaxChunks,
                    IncludeContext = true,
                    UseVectorSearch = queryEmbedding != null,
                    QueryEmbedding = queryEmbedding
                };

                var searchResult = await _chunkSearchService.SearchChunksAsync(searchRequest, cancellationToken);
                chunks = searchResult.Items
                    .Where(c => c.RelevanceScore >= request.MinRelevanceScore)
                    .ToList();

                _logger.LogInformation("Found {Count} relevant chunks (of {Total} searched, min score {MinScore}) for query: {Query}",
                    chunks.Count, searchResult.Items.Count(), request.MinRelevanceScore, request.Message);
            }
            catch (Exception ex)
            {
                _logger.LogWarning(ex, "Chunk search failed for query '{Query}', proceeding without document context",
                    request.Message);
            }

            // 3. Build context from retrieved chunks
            var contextBuilder = new StringBuilder();
            string systemPrompt;

            if (chunks.Count > 0)
            {
                contextBuilder.AppendLine("Here are relevant excerpts from the Epstein document files:");
                contextBuilder.AppendLine();

                foreach (var chunk in chunks)
                {
                    contextBuilder.AppendLine($"[Source: {chunk.EftaNumber ?? $"Doc-{chunk.DocumentId}"}, Page {chunk.PageNumber ?? 0}]");
                    contextBuilder.AppendLine(chunk.ChunkText ?? chunk.Snippet ?? string.Empty);
                    contextBuilder.AppendLine();
                }

                systemPrompt = @"You are an expert analyst helping investigate the Epstein case files.
Your task is to answer questions based ONLY on the document excerpts provided.
Always cite your sources using the document identifiers (EFTA numbers).
If the answer is not in the provided context, say so clearly.
Be precise and factual. Do not speculate beyond what the documents show.
Note any redacted content that may affect your answer.";
            }
            else
            {
                _logger.LogInformation("No document chunks found, generating response with general knowledge");
                systemPrompt = @"You are an expert analyst helping investigate the Epstein case files.
Note: Document search is currently unavailable, so you cannot reference specific documents.
Please provide helpful information based on your general knowledge about the Epstein case,
but clearly note that you are not citing specific documents from the database.
If the user needs specific document references, suggest they try again later when document search is available.";
            }

            // 3. Build messages for OpenAI
            var messages = new List<object>
            {
                new
                {
                    role = "system",
                    content = systemPrompt
                }
            };

            // Add conversation history if provided
            if (request.History != null)
            {
                foreach (var historyItem in request.History.TakeLast(6))
                {
                    messages.Add(new
                    {
                        role = historyItem.Role.ToLowerInvariant(),
                        content = historyItem.Content
                    });
                }
            }

            // Add current message with context (if available)
            var userContent = chunks.Count > 0
                ? $"{contextBuilder}\n\nQuestion: {request.Message}"
                : request.Message;

            messages.Add(new
            {
                role = "user",
                content = userContent
            });

            // 4. Call OpenAI API
            var openAiRequest = new
            {
                model = "gpt-4o-mini",
                messages = messages,
                max_tokens = 1500,
                temperature = 0.3
            };

            _httpClient.DefaultRequestHeaders.Clear();
            _httpClient.DefaultRequestHeaders.Add("Authorization", $"Bearer {apiKey}");

            var response = await _httpClient.PostAsJsonAsync(
                "https://api.openai.com/v1/chat/completions",
                openAiRequest,
                cancellationToken);

            if (!response.IsSuccessStatusCode)
            {
                var errorContent = await response.Content.ReadAsStringAsync(cancellationToken);
                _logger.LogError("OpenAI API error: {StatusCode} - {Content}", response.StatusCode, errorContent);
                return StatusCode(502, $"AI service error: {response.StatusCode}");
            }

            var responseJson = await response.Content.ReadFromJsonAsync<JsonElement>(cancellationToken);

            var answer = responseJson
                .GetProperty("choices")[0]
                .GetProperty("message")
                .GetProperty("content")
                .GetString() ?? "Unable to generate response.";

            TokenUsage? tokenUsage = null;
            if (responseJson.TryGetProperty("usage", out var usage))
            {
                tokenUsage = new TokenUsage
                {
                    Input = usage.GetProperty("prompt_tokens").GetInt32(),
                    Output = usage.GetProperty("completion_tokens").GetInt32()
                };
            }

            return Ok(new ChatResponse
            {
                Answer = answer,
                Sources = _mapper.Map<List<ChunkSearchResultDto>>(chunks),
                TokensUsed = tokenUsage
            });
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error processing chat completion");
            return StatusCode(500, "An error occurred processing your request.");
        }
    }

    [HttpGet("status")]
    public async Task<ActionResult<object>> GetStatus(CancellationToken cancellationToken = default)
    {
        var hasApiKey = !string.IsNullOrEmpty(_configuration["OpenAI:ApiKey"])
            || !string.IsNullOrEmpty(Environment.GetEnvironmentVariable("OPENAI_API_KEY"));

        try
        {
            var chunkStats = await _chunkSearchService.GetStatsAsync(cancellationToken);

            return Ok(new
            {
                ApiConfigured = hasApiKey,
                ChunksAvailable = chunkStats.TotalChunks > 0,
                TotalChunks = chunkStats.TotalChunks,
                FtsAvailable = chunkStats.FtsAvailable,
                VectorSearchAvailable = chunkStats.VectorSearchAvailable
            });
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Failed to get chunk stats - chunk search may not be available");
            return Ok(new
            {
                ApiConfigured = hasApiKey,
                ChunksAvailable = false,
                TotalChunks = 0,
                FtsAvailable = false,
                VectorSearchAvailable = false,
                Message = "Chunk search not available on this database configuration"
            });
        }
    }

    /// <summary>
    /// Generates an embedding vector for the user's query using the local embedding service.
    /// Uses the same model (all-MiniLM-L6-v2, 384 dimensions) that created the chunk embeddings.
    /// </summary>
    private async Task<float[]?> GetQueryEmbeddingAsync(
        string query,
        string apiKey,
        CancellationToken cancellationToken)
    {
        // Try local embedding service first (uses same model as chunk embeddings)
        var localEmbedding = await GetLocalEmbeddingAsync(query, cancellationToken);
        if (localEmbedding != null)
        {
            return localEmbedding;
        }

        // Fall back to OpenAI if local service unavailable
        _logger.LogWarning("Local embedding service unavailable, falling back to OpenAI");
        return await GetOpenAIEmbeddingAsync(query, apiKey, cancellationToken);
    }

    /// <summary>
    /// Gets embedding from the local Python service (all-MiniLM-L6-v2, 384 dimensions).
    /// This matches the model used to create the chunk embeddings in the database.
    /// </summary>
    private async Task<float[]?> GetLocalEmbeddingAsync(
        string query,
        CancellationToken cancellationToken)
    {
        try
        {
            // VM embedding service - use SSH tunnel: ssh -L 5050:localhost:5050 azureuser@20.25.96.123
            // Or open port 5050 in Azure NSG and use: http://20.25.96.123:5050
            var embeddingServiceUrl = _configuration["EmbeddingService:Url"] ?? "http://localhost:5050";

            using var client = new HttpClient { Timeout = TimeSpan.FromSeconds(10) };
            var response = await client.PostAsJsonAsync(
                $"{embeddingServiceUrl}/embed",
                new { text = query },
                cancellationToken);

            if (response.IsSuccessStatusCode)
            {
                var responseJson = await response.Content.ReadFromJsonAsync<JsonElement>(cancellationToken);
                var embeddingArray = responseJson.GetProperty("embedding");

                var embedding = new float[embeddingArray.GetArrayLength()];
                int i = 0;
                foreach (var value in embeddingArray.EnumerateArray())
                {
                    embedding[i++] = value.GetSingle();
                }

                _logger.LogDebug("Generated local embedding with {Dimensions} dimensions", embedding.Length);
                return embedding;
            }

            _logger.LogWarning("Local embedding service returned {StatusCode}", response.StatusCode);
            return null;
        }
        catch (Exception ex)
        {
            _logger.LogDebug(ex, "Local embedding service not available");
            return null;
        }
    }

    /// <summary>
    /// Gets embedding from OpenAI API (text-embedding-3-small, 1536 dimensions).
    /// Note: These embeddings are NOT compatible with the local model embeddings.
    /// </summary>
    private async Task<float[]?> GetOpenAIEmbeddingAsync(
        string query,
        string apiKey,
        CancellationToken cancellationToken)
    {
        try
        {
            var embeddingRequest = new
            {
                model = "text-embedding-3-small",
                input = query
            };

            _httpClient.DefaultRequestHeaders.Clear();
            _httpClient.DefaultRequestHeaders.Add("Authorization", $"Bearer {apiKey}");

            var response = await _httpClient.PostAsJsonAsync(
                "https://api.openai.com/v1/embeddings",
                embeddingRequest,
                cancellationToken);

            if (response.IsSuccessStatusCode)
            {
                var responseJson = await response.Content.ReadFromJsonAsync<JsonElement>(cancellationToken);
                var embeddingArray = responseJson
                    .GetProperty("data")[0]
                    .GetProperty("embedding");

                var embedding = new float[embeddingArray.GetArrayLength()];
                int i = 0;
                foreach (var value in embeddingArray.EnumerateArray())
                {
                    embedding[i++] = value.GetSingle();
                }

                return embedding;
            }

            var errorContent = await response.Content.ReadAsStringAsync(cancellationToken);
            _logger.LogWarning("Failed to generate OpenAI embedding: {StatusCode} - {Error}",
                response.StatusCode, errorContent);
            return null;
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Error generating OpenAI embedding");
            return null;
        }
    }
}
