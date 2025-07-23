// --- Add these 'using' statements at the top ---
using Jobvago.Api.Data;
using Microsoft.EntityFrameworkCore;

var builder = WebApplication.CreateBuilder(args);

// --- Section 1: Configure Services ---

// Get the connection string from appsettings.json
var connectionString = builder.Configuration.GetConnectionString("DefaultConnection");

// Register our DbContext for Dependency Injection.
// This tells the app how to connect to the database.
builder.Services.AddDbContext<JobvagoDbContext>(options =>
    options.UseSqlServer(connectionString));

// Add the services required to use API Controllers.
builder.Services.AddControllers();

// Add services for Swagger/OpenAPI, which provides the interactive test page for our API.
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();


// --- Section 2: Build the Application ---
var app = builder.Build();


// --- Section 3: Configure the HTTP Request Pipeline ---

// Enable the Swagger UI only when in the Development environment.
if (app.Environment.IsDevelopment())
{
    app.UseSwagger();
    app.UseSwaggerUI();
}

// Redirect HTTP requests to HTTPS for security.
app.UseHttpsRedirection();

// This is the crucial line that maps the routes from our Controller files (e.g., JobsController.cs).
app.MapControllers();

// Run the application.
app.Run();