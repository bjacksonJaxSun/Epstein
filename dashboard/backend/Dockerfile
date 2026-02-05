FROM mcr.microsoft.com/dotnet/aspnet:9.0 AS base
WORKDIR /app
EXPOSE 5000

FROM mcr.microsoft.com/dotnet/sdk:9.0 AS build
WORKDIR /src
COPY ["src/EpsteinDashboard.Core/EpsteinDashboard.Core.csproj", "src/EpsteinDashboard.Core/"]
COPY ["src/EpsteinDashboard.Application/EpsteinDashboard.Application.csproj", "src/EpsteinDashboard.Application/"]
COPY ["src/EpsteinDashboard.Infrastructure/EpsteinDashboard.Infrastructure.csproj", "src/EpsteinDashboard.Infrastructure/"]
COPY ["src/EpsteinDashboard.Api/EpsteinDashboard.Api.csproj", "src/EpsteinDashboard.Api/"]
RUN dotnet restore "src/EpsteinDashboard.Api/EpsteinDashboard.Api.csproj"
COPY . .
WORKDIR "/src/src/EpsteinDashboard.Api"
RUN dotnet publish -c Release -o /app/publish /p:UseAppHost=false

FROM base AS final
WORKDIR /app
COPY --from=build /app/publish .
ENV ASPNETCORE_URLS=http://+:5000
ENV ASPNETCORE_ENVIRONMENT=Production
ENTRYPOINT ["dotnet", "EpsteinDashboard.Api.dll"]
