package demo

func LiveExported() {
	println("live")
}

func Multiline(flag bool) {
	isOneWay :=
		false
	use(isOneWay)
}

func use(b bool) { println(b) }
