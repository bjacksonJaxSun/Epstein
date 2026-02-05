using AutoMapper;
using EpsteinDashboard.Application.DTOs;
using EpsteinDashboard.Core.Interfaces;
using EpsteinDashboard.Core.Models;

namespace EpsteinDashboard.Application.Services;

public class NetworkAnalysisService
{
    private readonly IGraphQueryService _graphQueryService;
    private readonly IMapper _mapper;

    public NetworkAnalysisService(IGraphQueryService graphQueryService, IMapper mapper)
    {
        _graphQueryService = graphQueryService;
        _mapper = mapper;
    }

    public async Task<NetworkGraphDto> GetPersonNetworkAsync(long personId, int depth = 2, CancellationToken cancellationToken = default)
    {
        var graph = await _graphQueryService.GetNetworkGraphAsync(personId, depth, cancellationToken);
        return _mapper.Map<NetworkGraphDto>(graph);
    }

    public async Task<ConnectionPath> FindConnectionAsync(long person1Id, long person2Id, int maxDepth = 6, CancellationToken cancellationToken = default)
    {
        return await _graphQueryService.FindConnectionPathAsync(person1Id, person2Id, maxDepth, cancellationToken);
    }
}
