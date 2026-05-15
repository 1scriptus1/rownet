// main.gi — the example from the GI spec


func main() {
    print("hello, world!")
    hook()
}

func hook() {
    main()
    print("hello, world!")
}

main()