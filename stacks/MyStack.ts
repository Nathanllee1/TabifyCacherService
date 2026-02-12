import { StackContext, Api, EventBus, Function, Table } from "sst/constructs";

export function API({ stack }: StackContext) {

  const table = new Table(
    stack,
    "Cache",
    {
      primaryIndex: {
        partitionKey: "spotifyId"
      },
      fields: {
        inUG: "binary",
        spotifyId: "string"
      }
    }
  )

  const func = new Api(stack, "Handler",  {
    routes: {
      "GET /api": {
        function: {
          handler: "./src/get/handler.main",
          runtime: "python3.11",
        }
      },
      "GET /onug": {
        function: {
          handler: "./src/onug/on_ug.handler",
          permissions: [table],
          bind: [table]
        }
      }
    },
    cors: {
      allowMethods: ["ANY"],
      allowHeaders: ["Authorization"],
      allowOrigins: ["*", "http://localhost:3000"],
    },
    
  })

  stack.addOutputs({
    FuncEndpoint: func.url,
  });
}
