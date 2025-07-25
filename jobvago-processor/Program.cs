using Microsoft.Azure.Functions.Worker;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.EntityFrameworkCore;
using System;
using Jobvago.Api.Data;

var host = new HostBuilder()
    .ConfigureFunctionsWorkerDefaults()
    .ConfigureServices(services =>
    {
        services.AddApplicationInsightsTelemetryWorkerService();
        services.ConfigureFunctionsApplicationInsights();

        string connectionString = Environment.GetEnvironmentVariable("SqlConnectionString")!;
        services.AddDbContext<JobvagoDbContext>(options =>
            options.UseSqlServer(connectionString));
    })
    .Build();

host.Run();